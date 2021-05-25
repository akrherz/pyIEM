"""TAF Parsing"""
# stdlib
from datetime import timedelta
import re

# local
from pyiem.nws.product import TextProduct
from pyiem import reference
from pyiem.models.taf import TAFForecast, TAFReport, SkyCondition, WindShear

TEMPO_TIME = re.compile(r"^(?P<ddhh1>\d{4})/(?P<ddhh2>\d{4}) ")
STID_VALID = re.compile(r"(?P<station>[A-Z0-9]{4}) (?P<ddhhmi>\d{6})Z")
WIND_RE = re.compile(r"(?P<dir>\d{3})(?P<sknt>\d{2,3})G?(?P<gust>\d{2,3})?KT")
VIS_RE = re.compile(r" (?P<over>P?)(?P<miles>[1-6])?\s?(?P<frac>\d/\d+)?SM")
WX_RE = re.compile(r"^([\-\+A-Z]+)$")
CLOUD_RE = re.compile(r" (?P<skyc>SCT|OVC|VV|BKN|FEW)(?P<skyl>\d{3})")
SHEAR_RE = re.compile(
    r" WS(?P<level>\d{3})/(?P<drct>\d{3})(?P<sknt>\d{2,3})KT"
)


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
    fx.presentwx = [x for x in text.split() if WX_RE.match(x)]

    for token in CLOUD_RE.findall(text):
        fx.sky.append(SkyCondition(amount=token[0], level=int(token[1]) * 100))

    for token in SHEAR_RE.findall(text):
        fx.shear = WindShear(
            level=int(token[0]) * 100,
            drct=int(token[1]),
            sknt=int(token[2]),
        )


def make_tempo(prod, text):
    """Parse a tempo group."""
    text = text.replace("TEMPO ", "")
    # Convert the ddhr/ddhr
    m = TEMPO_TIME.search(text)
    if m is None:
        return None
    d = m.groupdict()
    sts = ddhhmi2valid(prod, d["ddhh1"] + "00")
    ets = ddhhmi2valid(prod, d["ddhh2"] + "00")

    fx = TAFForecast(
        valid=sts,
        end_valid=ets,
        raw=text.replace("=", "").strip(),
        istempo=True,
    )
    add_forecast_info(fx, text)
    return fx


def make_forecast(prod, text):
    """Build a TAFForecast data model."""
    valid = ddhhmi2valid(prod, text[2:8])
    fx = TAFForecast(
        valid=valid,
        raw=text.replace("=", "").strip(),
    )
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


def parse_prod(prod):
    """Generate a data object from this product."""
    m = STID_VALID.search(prod.unixtext)
    d = m.groupdict()
    meat = ""
    tokens = []
    parts = prod.unixtext[m.end() : prod.unixtext.find("=")].split("\n")
    # Deal with the observation
    valid = ddhhmi2valid(prod, d["ddhhmi"])
    data = TAFReport(
        station=d["station"],
        valid=valid,
        product_id=prod.get_product_id(),
        observation=TAFForecast(
            valid=valid,
            raw=parts[0].strip(),
        ),
    )
    add_forecast_info(data.observation, parts[0])

    # Deal with the forecast detail
    for line in parts[1:]:
        ls = line.strip()
        if ls.startswith("FM") or ls.startswith("TEMPO"):
            if meat != "":
                tokens.append(meat.strip())
            meat = line
        else:
            meat += line
    if meat != "":
        tokens.append(meat.strip())
    for token in tokens:
        func = make_forecast if token.startswith("FM") else make_tempo
        forecast = func(prod, token)
        if forecast is not None:
            data.forecasts.append(forecast)

    return data


class TAFProduct(TextProduct):
    """
    Represents a TAF
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
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
        taf_id = txn.fetchone()[0]
        # Insert obs / forecast
        for entry in [taf.observation, *taf.forecasts]:
            txn.execute(
                "INSERT into taf_forecast(taf_id, valid, raw, is_tempo, "
                "end_valid, sknt, drct, gust, visibility, presentwx, skyc, "
                "skyl, ws_level, ws_drct, ws_sknt) VALUES (%s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    taf_id,
                    entry.valid,
                    entry.raw,
                    entry.istempo,
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
                ),
            )

    def get_jabbers(self, uri, _uri2=None):
        """Get the jabber variant of this message"""
        res = []
        url = f"{uri}?pid={self.get_product_id()}"
        aaa = "TAF"
        nicedate = self.get_nicedate()
        plain = "%s issues %s (%s) at %s for %s %s" % (
            self.source[1:],
            reference.prodDefinitions.get(aaa, aaa),
            aaa,
            nicedate,
            self.data.station[1:],
            url,
        )
        html = '<p>%s issues <a href="%s">%s (%s)</a> at %s for %s</p>' % (
            self.source[1:],
            url,
            reference.prodDefinitions.get(aaa, aaa),
            aaa,
            nicedate,
            self.data.station[1:],
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
