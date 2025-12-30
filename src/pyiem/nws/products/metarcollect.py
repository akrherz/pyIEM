"""Encapsulates a text product holding METARs."""

import re
from datetime import timedelta, timezone
from typing import Tuple
from zoneinfo import ZoneInfo

from metar.Metar import Metar
from metar.Metar import ParserError as MetarParserError

from pyiem import datatypes
from pyiem.nws.product import TextProduct
from pyiem.observation import Observation
from pyiem.reference import TRACE_VALUE, TWEET_CHARS
from pyiem.util import LOG, drct2text

NIL_RE = re.compile(r"[\s\n]NIL")
ERROR_RE = re.compile("Unparsed groups in body '(?P<msg>.*)' while processing")
TORNADO_RE = re.compile(r" \+FC |TORNADO")
FUNNEL_RE = re.compile(r" FC |FUNNEL")
# Match what looks like SA formatted messages
SA_RE = re.compile(r"^[A-Z]{3}\sSA")
# Sites we should route to Jabber
JABBER_SITES = {}
# Keep track of Wind alerts to prevent dups
WIND_ALERTS = {}
# Wind speed threshold in kts for alerting
WIND_ALERT_THRESHOLD_KTS = 50.0
# Per site thresholds to govern mapping to channels
WIND_ALERT_THRESHOLD_KTS_BY_ICAO = {}


def normalize_temp(val):
    """When temperatures are close to an int, return that int!"""
    rounded = round(val, 0)
    return int(rounded) if abs(val - rounded) < 0.199 else round(val, 1)


def normid(station_id: str) -> str:
    """Normalize a station identifer."""
    if len(station_id) == 4 and station_id.startswith("K"):
        return station_id[1:]
    return station_id


def wind_logic(iem, mtr: Metar):
    """Hairy logic for now we handle winds."""
    # Explicit storages
    if mtr.wind_speed:
        iem.data["sknt"] = mtr.wind_speed.value("KT")
    if mtr.wind_gust:
        iem.data["gust"] = mtr.wind_gust.value("KT")
    if mtr.wind_dir:
        iem.data["drct"] = float(mtr.wind_dir.value())
    if mtr.wind_speed_peak:
        iem.data["peak_wind_gust"] = mtr.wind_speed_peak.value("KT")
    if mtr.wind_dir_peak:
        iem.data["peak_wind_drct"] = mtr.wind_dir_peak.value()
    if mtr.peak_wind_time:
        # python-metar has an edge case for events crossing a month
        if mtr.peak_wind_time > mtr.time:
            mtr.peak_wind_time = mtr.peak_wind_time.replace(
                year=mtr.time.year, month=mtr.time.month
            )
        iem.data["peak_wind_time"] = mtr.peak_wind_time.replace(
            tzinfo=timezone.utc
        )

    # Figure out if we have a new max_drct
    old_max_wind = max(
        [iem.data.get("max_sknt", 0) or 0, iem.data.get("max_gust", 0) or 0]
    )
    new_max_wind = max(
        [iem.data.get("sknt", 0) or 0, iem.data.get("gust", 0) or 0]
    )
    # if our sknt or gust is a new max, use drct
    if new_max_wind > old_max_wind:
        iem.data["max_drct"] = iem.data.get("drct", 0)
    # if our PK WND is greater than all yall, use PK WND
    # TODO: PK WND potentially could be from last hour / thus yesterday?
    if (
        mtr.wind_speed_peak
        and mtr.wind_dir_peak
        and mtr.wind_speed_peak.value("KT") > old_max_wind
        and mtr.wind_speed_peak.value("KT") > new_max_wind
    ):
        iem.data["max_drct"] = mtr.wind_dir_peak.value()
        iem.data["max_gust_ts"] = mtr.peak_wind_time.replace(
            tzinfo=timezone.utc
        )
        iem.data["max_gust"] = mtr.wind_speed_peak.value("KT")


def trace(pobj):
    """Convert this precip object to a numeric value"""
    if pobj is None:
        return None
    val = pobj.value("IN")
    if val == 0:
        # IEM denotation of trace
        return TRACE_VALUE
    return val


def to_metar(textprod, text) -> Metar:
    """Create a METAR object, if possible"""
    # Do some cleaning and whitespace trimming
    text = sanitize(text)
    if len(text) < 14:  # arb
        return None
    attempt = 1
    mtr = None
    original_text = text
    valid = textprod.valid
    while attempt < 6 and mtr is None:
        try:
            mtr = Metar(text, month=valid.month, year=valid.year)
        except MetarParserError as inst:
            tokens = ERROR_RE.findall(str(inst))
            if tokens:
                if tokens[0] == text or text.startswith(tokens[0]):
                    return None
                # So tokens contains a series of groups that needs updated
                newtext = text
                for token in tokens[0].split():
                    newtext = newtext.replace(f" {token}", "")
                if newtext != text:
                    text = newtext
            # Somewhat brittle logic checking exception message
            if "day" in str(inst) and "range" in str(inst) and valid.day < 10:
                valid = valid.replace(day=1) - timedelta(days=1)
        attempt += 1

    if mtr is not None:
        # Attempt to figure out more things
        if mtr.station_id is None:
            LOG.warning("Aborting due to station_id being None |%s|", text)
            return None
        if mtr.time is None:
            LOG.warning("Aborting due to time being None |%s|", text)
            return None
        # don't allow data more than an hour into the future
        ceiling = (textprod.utcnow + timedelta(hours=1)).replace(tzinfo=None)
        if mtr.time > ceiling:
            # careful, we may have obs from the previous month
            if ceiling.day < 5 and mtr.time.day > 15:
                prevmonth = ceiling - timedelta(days=10)
                mtr.time = mtr.time.replace(
                    year=prevmonth.year, month=prevmonth.month
                )
            else:
                LOG.warning(
                    "Aborting due to time in the future "
                    "ceiling: %s mtr.time: %s",
                    ceiling,
                    mtr.time,
                )
                return None
        mtr.code = original_text
    return mtr


def sanitize(text):
    """Clean our text string with METAR data"""
    text = re.sub("\015", " ", text)
    # Remove any multiple whitespace, bad chars
    text = (
        text.encode("utf-8", "ignore")
        .replace(b"\xa0", b" ")
        .replace(b"\001", b"")
        .replace(b"\003", b"")
        .decode("utf-8", errors="ignore")
    )
    text = " ".join(text.strip().split())
    # Look to see that our METAR starts with A-Z
    if re.match("^[0-9]", text):
        tokens = text.split()
        text = " ".join(tokens[1:])
    return text


def _is_same_day(valid, tzname, hours=6):
    """Can we trust a six hour total?"""
    try:
        tzinfo = ZoneInfo(tzname)
    except Exception:
        return False
    lts = valid.astimezone(tzinfo)
    # TODO we should likely somehow compute this in standard time, shrug
    return lts.day == (lts - timedelta(hours=hours)).day


def wind_message(mtr: Metar) -> Tuple[str, int]:
    """Convert this into a Jabber style message"""
    drct = 0
    sknt = 0
    time = mtr.time.replace(tzinfo=timezone.utc)
    if mtr.wind_gust:
        sknt = mtr.wind_gust.value("KT")
        if mtr.wind_dir:
            drct = mtr.wind_dir.value()
    if mtr.wind_speed_peak:
        v1 = mtr.wind_speed_peak.value("KT")
        d1 = mtr.wind_dir_peak.value()
        t1 = mtr.peak_wind_time.replace(tzinfo=timezone.utc)
        if v1 > sknt:
            sknt = v1
            drct = d1
            time = t1
    key = f"{mtr.station_id};{sknt};{time}"
    if key in WIND_ALERTS:
        return None, None
    WIND_ALERTS[key] = 1
    speed = datatypes.speed(sknt, "KT")
    msg = (
        f"gust of {speed.value('KT'):.0f} knots "
        f"({speed.value('MPH'):.1f} mph) from {drct2text(drct)} @ {time:%H%M}Z"
    )
    return msg, int(speed.value("KT"))


def over_wind_threshold(mtr: Metar) -> bool:
    """Is this METAR over the wind threshold for alerting"""
    if mtr.wind_gust and mtr.wind_gust.value("KT") >= WIND_ALERT_THRESHOLD_KTS:
        return True
    if (
        mtr.wind_speed_peak
        and mtr.wind_speed_peak.value("KT") >= WIND_ALERT_THRESHOLD_KTS
    ):
        return True
    return False


def to_iemaccess(
    txn,
    mtr: Metar,
    iemid: int,
    tzname: str,
    force_current_log=False,
    skip_current=False,
):
    """Persist parsed data to IEMAccess Database.

    Args:
        txn (psycopg.cursor): database cursor / transaction
        mtr (Metar): Metar instance
        iemid: The iem station identifier
        tzname (str): Local timezone of station.
        force_current_log (boolean): should this ob always go to current_log
        skip_current (boolean): should this ob always skip current table
    """
    gts = mtr.time.replace(tzinfo=timezone.utc)
    iem = Observation(valid=gts, iemid=iemid, tzname=tzname)
    # Load the observation from the database, if the same time exists!
    iem.load(txn)

    # Need to figure out if we have a duplicate ob, if so, check
    # the length of the raw data, if greater, take the temps
    if iem.data["raw"] is None or len(iem.data["raw"]) < len(mtr.code):
        if mtr.temp:
            val = mtr.temp.value("F")
            # Place reasonable bounds on the temperature before saving it!
            if -90 < val < 150:
                iem.data["tmpf"] = normalize_temp(val)
        if mtr.dewpt:
            val = mtr.dewpt.value("F")
            # Place reasonable bounds on the temperature before saving it!
            if -150 < val < 100:
                iem.data["dwpf"] = normalize_temp(val)
        # Database only allows len 254
        iem.data["raw"] = mtr.code[:254]
    # Always take a COR
    if mtr.code.find(" COR ") > -1:
        iem.data["raw"] = mtr.code[:254]

    wind_logic(iem, mtr)

    if mtr.max_temp_6hr:
        iem.data["max_tmpf_6hr"] = normalize_temp(mtr.max_temp_6hr.value("F"))
        if tzname and _is_same_day(iem.data["valid"], tzname):
            iem.data["max_tmpf_cond"] = iem.data["max_tmpf_6hr"]
    if mtr.min_temp_6hr:
        iem.data["min_tmpf_6hr"] = normalize_temp(mtr.min_temp_6hr.value("F"))
        if tzname and _is_same_day(iem.data["valid"], tzname):
            iem.data["min_tmpf_cond"] = iem.data["min_tmpf_6hr"]
    if mtr.max_temp_24hr:
        iem.data["max_tmpf_24hr"] = normalize_temp(
            mtr.max_temp_24hr.value("F")
        )
    if mtr.min_temp_24hr:
        iem.data["min_tmpf_24hr"] = normalize_temp(
            mtr.min_temp_24hr.value("F")
        )
    if mtr.precip_3hr:
        iem.data["p03i"] = trace(mtr.precip_3hr)
    if mtr.precip_6hr:
        iem.data["p06i"] = trace(mtr.precip_6hr)
    if mtr.precip_24hr:
        iem.data["p24i"] = trace(mtr.precip_24hr)
    # We assume the value is zero, sad!
    iem.data["phour"] = 0
    if mtr.precip_1hr:
        iem.data["phour"] = trace(mtr.precip_1hr)

    if mtr.snowdepth:
        # NOTE snowd is a summary variable that wants to be daily, this
        # METAR value is more instantaneous, so goes to current table
        iem.data["snowdepth"] = mtr.snowdepth.value("IN")
    if mtr.vis:
        iem.data["vsby"] = mtr.vis.value("SM")
    if mtr.press:
        iem.data["alti"] = mtr.press.value("IN")
    if mtr.press_sea_level:
        iem.data["mslp"] = mtr.press_sea_level.value("MB")
    if mtr.press_sea_level and mtr.press:
        alti = mtr.press.value("MB")
        mslp = mtr.press_sea_level.value("MB")
        if abs(alti - mslp) > 25:
            LOG.warning(
                "PRESSURE ERROR %s %s ALTI: %s MSLP: %s",
                mtr.station_id,
                iem.data["valid"],
                alti,
                mslp,
            )
            if alti > mslp:
                iem.data["mslp"] += 100.0
            else:
                iem.data["mslp"] -= 100.0
    # Do something with sky coverage
    for i, (cov, hgh, _) in enumerate(mtr.sky, start=1):
        iem.data[f"skyc{i}"] = cov
        if hgh is not None:
            iem.data[f"skyl{i}"] = int(hgh.value("FT"))

    # Presentwx
    if mtr.weather:
        pwx = []
        for wx in mtr.weather:
            val = "".join([a for a in wx if a is not None])
            if val in ["", len(val) * "/"]:
                continue
            pwx.append(val)
        iem.data["wxcodes"] = pwx

    # Ice Accretion
    for hr in [1, 3, 6]:
        key = f"ice_accretion_{hr}hr"
        iem.data[key] = trace(getattr(mtr, key))
    return iem, iem.save(txn, force_current_log, skip_current)


class METARCollective(TextProduct):
    """
    A TextProduct containing METAR information
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """Constructor

        Args:
          text (string): the raw string to process"""
        super().__init__(text, utcnow, ugc_provider, nwsli_provider)
        self.metars = []
        self.split_and_parse()

    def get_jabbers(self, uri, _uri2=None):
        """Make this into jabber messages"""
        jmsgs = []
        for mtr in self.metars:
            msg = None
            sknt = 0
            for weatheri in mtr.weather:
                for wx in weatheri:
                    if wx is not None and "GR" in wx:
                        msg = "Hail"
            if TORNADO_RE.findall(mtr.code):
                msg = "Tornado"
            elif FUNNEL_RE.findall(mtr.code):
                msg = "Funnel Cloud"
            # Search for Peak wind gust info....
            elif over_wind_threshold(mtr):
                msg, sknt = wind_message(mtr)
            # Sites set to always route to Jabber.
            if (
                mtr.station_id in JABBER_SITES
                and JABBER_SITES[mtr.station_id] != mtr.time
            ):
                JABBER_SITES[mtr.station_id] = mtr.time
                channels = [f"METAR.{mtr.station_id}"]
                if mtr.type == "SPECI":
                    channels.append(f"SPECI.{mtr.station_id}")
                mstr = f"{mtr.type} {mtr.code}"
                jmsgs.append([mstr, mstr, dict(channels=",".join(channels))])
            if msg is None:
                continue
            sid = normid(mtr.station_id)
            row = self.nwsli_provider.get(sid, {})
            wfo = row.get("wfo")
            if wfo is None or wfo == "":
                LOG.warning(
                    "Unknown WFO for %s, skipping alert", mtr.station_id
                )
                continue
            channels = [f"METAR.{mtr.station_id}"]
            if mtr.type == "SPECI":
                channels.append(f"SPECI.{mtr.station_id}")
            if sknt > 0:
                # Custom stuff for how this wind reports maps to channels
                if sknt >= WIND_ALERT_THRESHOLD_KTS_BY_ICAO.get(
                    mtr.station_id, WIND_ALERT_THRESHOLD_KTS
                ):
                    channels.append(wfo)
                # Thresholded channels
                for _sknt in range(
                    int(WIND_ALERT_THRESHOLD_KTS), sknt + 1, 10
                ):
                    channels.append(f"METAR.{mtr.station_id}.WIND{_sknt:.0f}")
            else:
                channels.append(wfo)
            st = row.get("state")
            nm = row.get("name")

            extra = ""
            if mtr.code.find("$") > 0:
                extra = "(Caution: Maintenance Check Indicator)"
            url = f"{uri}{row.get('network')}"
            jtxt = (
                f"{nm},{st} ({sid}) ASOS {extra} reports {msg}\n"
                f"{mtr.code} {url}"
            )
            jhtml = (
                f'<p><a href="{url}">{nm},{st}</a> ({sid}) ASOS '
                f"{extra} reports <strong>{msg}</strong>"
                f"<br/>{mtr.code}</p>"
            )
            xtra = {
                "channels": ",".join(channels),
                "lat": str(row.get("lat")),
                "long": str(row.get("lon")),
                "twitter": (
                    f"{nm},{st} ({sid}) ASOS reports {msg} -- {mtr.code}"
                )[:TWEET_CHARS],
            }
            jmsgs.append([jtxt, jhtml, xtra])

        return jmsgs

    def split_and_parse(self):
        """Create METAR objects as we find products in the text"""
        # unixtext is conditioned, so first line is LDM, WMO
        # the question is what is on the third line
        lines = self.unixtext.split("\n")
        # not METAR or SPECI, so take it
        linenum = 2 if len(lines[2].strip()) > 5 else 3
        content = "\n".join(lines[linenum:])
        # Tokenize on the '=', which splits a product with METARs
        tokens = content.split("=")
        for token in tokens:
            # Dump METARs that have NIL in them
            prefix = "METAR" if self.afos != "SPECI" else "SPECI"
            if NIL_RE.search(token):
                continue
            if token.find("METAR") > -1:
                token = token[(token.find("METAR") + 5) :]
            elif token.find("SPECI") > -1:
                token = token[(token.find("SPECI") + 5) :]
                prefix = "SPECI"
            elif len(token.strip()) < 5:
                continue
            res = to_metar(self, token)
            if res:
                res.type = prefix
                self.metars.append(res)


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function"""
    return METARCollective(text, utcnow, ugc_provider, nwsli_provider)
