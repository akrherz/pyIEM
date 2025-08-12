"""TAF Parsing"""

# stdlib
import re
from datetime import timedelta

from pyiem import reference
from pyiem.models.taf import SkyCondition, TAFForecast, TAFReport, WindShear

# local
from pyiem.nws.product import TextProduct

TEMPO_TIME = re.compile(r"^(?P<ddhh1>\d{4})/(?P<ddhh2>\d{4}) ")
STID_VALID = re.compile(r"(?P<station>[A-Z0-9]{4}) (?P<ddhhmi>\d{6})Z")
WIND_RE = re.compile(r"(?P<dir>\d{3})(?P<sknt>\d{2,3})G?(?P<gust>\d{2,3})?KT")
VIS_RE = re.compile(r" (?P<over>P?)(?P<miles>[1-6])?\s?(?P<frac>\d/\d+)?SM")
WX_RE = re.compile(r"^([\-\+A-Z]+)$")
CLOUD_RE = re.compile(r" (?P<skyc>SCT|OVC|VV|BKN|FEW)(?P<skyl>\d{3})")
SHEAR_RE = re.compile(
    r" WS(?P<level>\d{3})/(?P<drct>\d{3})(?P<sknt>\d{2,3})KT"
)

# Lame redefinition of what's in the database for ftype column
FTYPE = {
    "OB": 0,
    "FM": 1,
    "TEMPO": 2,
    "PROB30": 3,
    "PROB40": 4,
    "BECMG": 5,
}


def add_forecast_info(fx, text):
    """Common things."""
    m = WIND_RE.search(text)
    if m:
        d = m.groupdict()
        fx.sknt = int(d["sknt"])
        fx.drct = int(d["dir"])
        fx.gust = int(d["gust"] or 0)
    m = VIS_RE.search(text)
    if m:
        d = m.groupdict()
        fx.visibility = int(d["miles"] or 0)
        if d.get("over") == "P" and fx.visibility == 6:
            fx.visibility = reference.TAF_VIS_OVER_6SM
        if d["frac"] is not None:
            tokens = d["frac"].split("/")
            fx.visibility += float(tokens[0]) / float(tokens[1])
    # This may be too clever and saying anything without a number is presentwx
    fx.presentwx = [x for x in text.split() if WX_RE.match(x)]
    if "SKC" in fx.presentwx:
        fx.presentwx.remove("SKC")
        fx.sky.append(SkyCondition(amount="SKC", level=None))
    else:
        for token in CLOUD_RE.findall(text):
            fx.sky.append(
                SkyCondition(amount=token[0], level=int(token[1]) * 100)
            )

    for token in SHEAR_RE.findall(text):
        fx.shear = WindShear(
            level=int(token[0]) * 100,
            drct=int(token[1]),
            sknt=int(token[2]),
        )


def make_qualifier(prod: TextProduct, text: str, ftype_str: str):
    """Parse a tempo group."""
    text = text.replace(f"{ftype_str} ", "")
    # Convert the ddhr/ddhr
    m = TEMPO_TIME.search(text)
    if m is None:
        return None
    d = m.groupdict()
    sts = ddhhmi2valid(prod, d["ddhh1"] + "00")
    ets = ddhhmi2valid(prod, d["ddhh2"] + "00")

    fx = TAFForecast(
        ftype=FTYPE[ftype_str],
        valid=sts,
        end_valid=ets,
        raw=f"{ftype_str} {' '.join(text.split()).replace('=', '').strip()}",
    )  # type: ignore
    add_forecast_info(fx, text)
    return fx


def make_forecast(prod, text):
    """Build a TAFForecast data model."""
    valid = ddhhmi2valid(prod, text[2:8])
    fx = TAFForecast(
        valid=valid,
        raw=" ".join(text.split()).replace("=", "").strip(),
        ftype=FTYPE["FM"],
    )  # type: ignore
    add_forecast_info(fx, text)
    return fx


def ddhhmi2valid(prod, text):
    """Figure out what valid time this is."""
    dd = int(text[:2])
    hr = int(text[2:4])
    mi = int(text[4:6])
    if hr == 24:
        valid = prod.valid.replace(day=dd, hour=0, minute=mi) + timedelta(
            days=1
        )
    elif hr < 0 or hr > 23:
        raise ValueError(f"Found invalid hr: {hr} from '{text}'")
    else:
        valid = prod.valid.replace(hour=hr, minute=mi)
    # Next month
    if valid.day > 20 and dd < 3:
        valid += timedelta(days=14)
    elif valid.day == 1 and dd > 20:
        valid -= timedelta(days=14)
    if hr < 24:
        valid = valid.replace(day=dd)
    return valid


def parse_prod(prod: TextProduct):
    """Generate a data object from this product."""
    m = STID_VALID.search(prod.unixtext)
    d = m.groupdict()
    lines = []
    meat = prod.unixtext[m.end() : prod.unixtext.find("=")]
    accum = ""
    for token in [x.strip() for x in meat.splitlines()]:
        if token.startswith(("FM", "TEMPO", "BECMG", "PROB")):
            if accum != "":
                lines.append(accum)
            accum = token
        else:
            accum += f" {token}"
    if accum != "":
        lines.append(accum)
    # Deal with the observation
    valid = ddhhmi2valid(prod, d["ddhhmi"])
    data = TAFReport(
        station=d["station"],
        valid=valid,
        product_id=prod.get_product_id(),
        observation=TAFForecast(
            valid=valid,
            raw=" ".join(lines[0].split()).strip(),
            ftype=FTYPE["OB"],
        ),  # type: ignore
    )
    add_forecast_info(data.observation, lines[0])

    # Double check lines[0] for stuff
    parts = re.split(r"(TEMPO|PROB30|PROB40|BECMG)", lines[0])
    if len(parts) > 1:
        data.observation.raw = parts[0].strip()
        # Insert into lines
        lines.insert(1, f"{parts[1]} {parts[2]}")

    for token in lines[1:]:
        diction = None
        for part in re.split(r"(TEMPO|PROB30|PROB40|BECMG)", token):
            if part == "":
                continue
            if part.startswith("FM"):
                forecast = make_forecast(prod, part.strip())
                if forecast is not None:
                    data.forecasts.append(forecast)
                continue
            if diction is not None:
                forecast = make_qualifier(prod, part.strip(), diction)
                if forecast is not None:
                    data.forecasts.append(forecast)
                diction = None
                continue
            diction = part.strip()

    return data


class TAFProduct(TextProduct):
    """
    Represents a TAF
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        # Prevent expensive and unnecessary dblookup
        if ugc_provider is None:
            ugc_provider = {}
        super().__init__(text, utcnow, ugc_provider, nwsli_provider)
        self.data = parse_prod(self)

    def get_channels(self):
        """Return a list of channels"""
        return [f"TAF{self.data.station[1:]}", "TAF...", f"{self.source}.TAF"]

    def sql(self, txn):
        """Persist to the database."""
        taf = self.data
        # Product corrections are not really accounted for here due to
        # performance worries

        # Create an entry
        txn.execute(
            "INSERT into taf(station, valid, product_id) VALUES (%s, %s, %s) "
            "RETURNING id",
            (taf.station, taf.valid, self.get_product_id()),
        )
        taf_id = txn.fetchone()["id"]
        # Insert obs / forecast
        for entry in [taf.observation, *taf.forecasts]:
            txn.execute(
                "INSERT into taf_forecast(taf_id, valid, raw, is_tempo, "
                "end_valid, sknt, drct, gust, visibility, presentwx, skyc, "
                "skyl, ws_level, ws_drct, ws_sknt, ftype) VALUES "
                "(%s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    taf_id,
                    entry.valid,
                    entry.raw,
                    entry.ftype == FTYPE["TEMPO"],
                    entry.end_valid,
                    entry.sknt,
                    entry.drct,
                    entry.gust,
                    entry.visibility,
                    entry.presentwx,
                    [x.amount for x in entry.sky],
                    [x.level for x in entry.sky],
                    None if entry.shear is None else entry.shear.level,
                    None if entry.shear is None else entry.shear.drct,
                    None if entry.shear is None else entry.shear.sknt,
                    entry.ftype,
                ),
            )

    def get_jabbers(self, uri, _uri2=None):
        """Get the jabber variant of this message"""
        res = []
        url = f"{uri}?pid={self.get_product_id()}"
        aaa = "TAF"
        nicedate = self.get_nicedate()
        label = reference.prodDefinitions.get(aaa, aaa)
        plain = (
            f"{self.source[1:]} issues {label} ({aaa}) at {nicedate} for "
            f"{self.data.station[1:]} {url}"
        )
        html = (
            f'<p>{self.source[1:]} issues <a href="{url}">{label} ({aaa})</a> '
            f"at {nicedate} for {self.data.station[1:]}</p>"
        )
        xtra = {
            "channels": ",".join(self.get_channels()),
            "product_id": self.get_product_id(),
            "twitter": plain,
            "twitter_media": (
                "https://mesonet.agron.iastate.edu/plotting/auto/plot/219/"
                f"station:{self.data.station}::valid:"
                f"{self.data.valid.strftime('%Y-%m-%d%%20%H%M')}.png"
            ),
        }
        res.append((plain, html, xtra))
        return res


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function"""
    return TAFProduct(text, utcnow, ugc_provider, nwsli_provider)
