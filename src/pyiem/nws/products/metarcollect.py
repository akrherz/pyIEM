"""Encapsulates a text product holding METARs."""
import re
from datetime import timezone, timedelta

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo

from metar.Metar import Metar
from metar.Metar import ParserError as MetarParserError
from pyiem.nws.product import TextProduct
from pyiem.observation import Observation
from pyiem.reference import TRACE_VALUE, TWEET_CHARS
from pyiem import datatypes
from pyiem.util import drct2text, LOG

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


def wind_logic(iem, this):
    """Hairy logic for now we handle winds."""
    # Explicit storages
    if this.wind_speed:
        iem.data["sknt"] = this.wind_speed.value("KT")
    if this.wind_gust:
        iem.data["gust"] = this.wind_gust.value("KT")
    if this.wind_dir:
        iem.data["drct"] = float(this.wind_dir.value())
    if this.wind_speed_peak:
        iem.data["peak_wind_gust"] = this.wind_speed_peak.value("KT")
    if this.wind_dir_peak:
        iem.data["peak_wind_drct"] = this.wind_dir_peak.value()
    if this.peak_wind_time:
        iem.data["peak_wind_time"] = this.peak_wind_time.replace(
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
        this.wind_speed_peak
        and this.wind_dir_peak
        and this.wind_speed_peak.value("KT") > old_max_wind
        and this.wind_speed_peak.value("KT") > new_max_wind
    ):
        iem.data["max_drct"] = this.wind_dir_peak.value()
        iem.data["max_gust_ts"] = this.peak_wind_time.replace(
            tzinfo=timezone.utc
        )
        iem.data["max_gust"] = this.wind_speed_peak.value("KT")


def trace(pobj):
    """Convert this precip object to a numeric value"""
    if pobj is None:
        return None
    val = pobj.value("IN")
    if val == 0:
        # IEM denotation of trace
        return TRACE_VALUE
    return val


def to_metar(textprod, text):
    """Create a METAR object, if possible"""
    # Do some cleaning and whitespace trimming
    text = sanitize(text)
    if len(text) < 14:  # arb
        return
    attempt = 1
    mtr = None
    original_text = text
    valid = textprod.valid
    while attempt < 6 and mtr is None:
        try:
            mtr = METARReport(text, month=valid.month, year=valid.year)
        except MetarParserError as inst:
            tokens = ERROR_RE.findall(str(inst))
            if tokens:
                if tokens[0] == text or text.startswith(tokens[0]):
                    return
                # So tokens contains a series of groups that needs updated
                newtext = text
                for token in tokens[0].split():
                    newtext = newtext.replace(" %s" % (token,), "")
                if newtext != text:
                    text = newtext
            if str(inst).find("day is out of range for month") > -1:
                if valid.day < 10:
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
        mtr.iemid = (
            mtr.station_id[-3:] if mtr.station_id[0] == "K" else mtr.station_id
        )
        mtr.network = textprod.nwsli_provider.get(mtr.iemid, {}).get("network")
        mtr.tzname = textprod.nwsli_provider.get(mtr.iemid, {}).get("tzname")
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


class METARReport(Metar):
    """Provide some additional functionality over baseline METAR"""

    def __init__(self, text, **kwargs):
        """Wrapper"""
        Metar.__init__(self, text, **kwargs)
        self.iemid = None
        self.network = None
        self.tzname = None

    def wind_message(self):
        """Convert this into a Jabber style message"""
        drct = 0
        sknt = 0
        time = self.time.replace(tzinfo=timezone.utc)
        if self.wind_gust:
            sknt = self.wind_gust.value("KT")
            if self.wind_dir:
                drct = self.wind_dir.value()
        if self.wind_speed_peak:
            v1 = self.wind_speed_peak.value("KT")
            d1 = self.wind_dir_peak.value()
            t1 = self.peak_wind_time.replace(tzinfo=timezone.utc)
            if v1 > sknt:
                sknt = v1
                drct = d1
                time = t1
        key = f"{self.station_id};{sknt};{time}"
        if key in WIND_ALERTS:
            return None
        WIND_ALERTS[key] = 1
        speed = datatypes.speed(sknt, "KT")
        return ("gust of %.0f knots (%.1f mph) from %s @ %s") % (
            speed.value("KT"),
            speed.value("MPH"),
            drct2text(drct),
            time.strftime("%H%MZ"),
        )

    def over_wind_threshold(self):
        """Is this METAR over the wind threshold for alerting"""
        if (
            self.wind_gust
            and self.wind_gust.value("KT") >= WIND_ALERT_THRESHOLD_KTS
        ):
            return True
        if (
            self.wind_speed_peak
            and self.wind_speed_peak.value("KT") >= WIND_ALERT_THRESHOLD_KTS
        ):
            return True
        return False

    def to_iemaccess(self, txn, force_current_log=False, skip_current=False):
        """Persist parsed data to IEMAccess Database.

        Args:
          txn (psycopg2.cursor): database cursor / transaction
          force_current_log (boolean): should this ob always go to current_log
          skip_current (boolean): should this ob always skip current table
        """
        gts = self.time.replace(tzinfo=timezone.utc)
        iem = Observation(self.iemid, self.network, gts)
        # Load the observation from the database, if the same time exists!
        iem.load(txn)

        # Need to figure out if we have a duplicate ob, if so, check
        # the length of the raw data, if greater, take the temps
        if iem.data["raw"] is None or len(iem.data["raw"]) < len(self.code):
            if self.temp:
                val = self.temp.value("F")
                # Place reasonable bounds on the temperature before saving it!
                if val > -90 and val < 150:
                    iem.data["tmpf"] = round(val, 1)
            if self.dewpt:
                val = self.dewpt.value("F")
                # Place reasonable bounds on the temperature before saving it!
                if val > -150 and val < 100:
                    iem.data["dwpf"] = round(val, 1)
            # Database only allows len 254
            iem.data["raw"] = self.code[:254]
        # Always take a COR
        if self.code.find(" COR ") > -1:
            iem.data["raw"] = self.code[:254]

        wind_logic(iem, self)

        if self.max_temp_6hr:
            iem.data["max_tmpf_6hr"] = round(self.max_temp_6hr.value("F"), 1)
            if self.tzname and _is_same_day(iem.data["valid"], self.tzname):
                iem.data["max_tmpf_cond"] = iem.data["max_tmpf_6hr"]
        if self.min_temp_6hr:
            iem.data["min_tmpf_6hr"] = round(self.min_temp_6hr.value("F"), 1)
            if self.tzname and _is_same_day(iem.data["valid"], self.tzname):
                iem.data["min_tmpf_cond"] = iem.data["min_tmpf_6hr"]
        if self.max_temp_24hr:
            iem.data["max_tmpf_24hr"] = round(self.max_temp_24hr.value("F"), 1)
        if self.min_temp_24hr:
            iem.data["min_tmpf_24hr"] = round(self.min_temp_24hr.value("F"), 1)
        if self.precip_3hr:
            iem.data["p03i"] = trace(self.precip_3hr)
        if self.precip_6hr:
            iem.data["p06i"] = trace(self.precip_6hr)
        if self.precip_24hr:
            iem.data["p24i"] = trace(self.precip_24hr)
        # We assume the value is zero, sad!
        iem.data["phour"] = 0
        if self.precip_1hr:
            iem.data["phour"] = trace(self.precip_1hr)

        if self.snowdepth:
            # NOTE snowd is a summary variable that wants to be daily, this
            # METAR value is more instantaneous, so goes to current table
            iem.data["snowdepth"] = self.snowdepth.value("IN")
        if self.vis:
            iem.data["vsby"] = self.vis.value("SM")
        if self.press:
            iem.data["alti"] = self.press.value("IN")
        if self.press_sea_level:
            iem.data["mslp"] = self.press_sea_level.value("MB")
        if self.press_sea_level and self.press:
            alti = self.press.value("MB")
            mslp = self.press_sea_level.value("MB")
            if abs(alti - mslp) > 25:
                LOG.warning(
                    "PRESSURE ERROR %s %s ALTI: %s MSLP: %s",
                    iem.data["station"],
                    iem.data["valid"],
                    alti,
                    mslp,
                )
                if alti > mslp:
                    iem.data["mslp"] += 100.0
                else:
                    iem.data["mslp"] -= 100.0
        # Do something with sky coverage
        for i in range(len(self.sky)):
            (cov, hgh, _) = self.sky[i]
            iem.data["skyc%s" % (i + 1)] = cov
            if hgh is not None:
                iem.data["skyl%s" % (i + 1)] = hgh.value("FT")

        # Presentwx
        if self.weather:
            pwx = []
            for wx in self.weather:
                val = "".join([a for a in wx if a is not None])
                if val == "" or val == len(val) * "/":
                    continue
                pwx.append(val)
            iem.data["wxcodes"] = pwx

        # Ice Accretion
        for hr in [1, 3, 6]:
            key = "ice_accretion_%shr" % (hr,)
            iem.data[key] = trace(getattr(self, key))
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
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.metars = []
        self.split_and_parse()

    def get_jabbers(self, uri, _uri2=None):
        """Make this into jabber messages"""
        jmsgs = []
        for mtr in self.metars:
            msg = None
            for weatheri in mtr.weather:
                for wx in weatheri:
                    if wx is not None and "GR" in wx:
                        msg = "Hail"
            if TORNADO_RE.findall(mtr.code):
                msg = "Tornado"
            elif FUNNEL_RE.findall(mtr.code):
                msg = "Funnel Cloud"
            # Search for Peak wind gust info....
            elif mtr.over_wind_threshold():
                _msg = mtr.wind_message()
                if _msg:
                    msg = _msg
            elif mtr.station_id in JABBER_SITES:
                # suck
                if JABBER_SITES[mtr.station_id] != mtr.time:
                    JABBER_SITES[mtr.station_id] = mtr.time
                    channels = ["METAR.%s" % (mtr.station_id,)]
                    if mtr.type == "SPECI":
                        channels.append("SPECI.%s" % (mtr.station_id,))
                    mstr = "%s %s" % (mtr.type, mtr.code)
                    jmsgs.append(
                        [mstr, mstr, dict(channels=",".join(channels))]
                    )
            if msg:
                row = self.nwsli_provider.get(mtr.iemid, {})
                wfo = row.get("wfo")
                if wfo is None or wfo == "":
                    LOG.warning(
                        "Unknown WFO for id: %s, skipping alert", mtr.iemid
                    )
                    continue
                channels = ["METAR.%s" % (mtr.station_id,)]
                if mtr.type == "SPECI":
                    channels.append("SPECI.%s" % (mtr.station_id,))
                channels.append(wfo)
                st = row.get("state")
                nm = row.get("name")

                extra = ""
                if mtr.code.find("$") > 0:
                    extra = "(Caution: Maintenance Check Indicator)"
                url = ("%s%s") % (uri, mtr.network)
                jtxt = ("%s,%s (%s) ASOS %s reports %s\n%s %s") % (
                    nm,
                    st,
                    mtr.iemid,
                    extra,
                    msg,
                    mtr.code,
                    url,
                )
                jhtml = (
                    f'<p><a href="{url}">{nm},{st}</a> ({mtr.iemid}) ASOS '
                    f"{extra} reports <strong>{msg}</strong>"
                    f"<br/>{mtr.code}</p>"
                )
                xtra = {
                    "channels": ",".join(channels),
                    "lat": str(row.get("lat")),
                    "long": str(row.get("lon")),
                }
                xtra["twitter"] = (
                    ("%s,%s (%s) ASOS reports %s -- %s")
                    % (nm, st, mtr.iemid, msg, mtr.code)
                )[:TWEET_CHARS]
                jmsgs.append([jtxt, jhtml, xtra])

        return jmsgs

    def split_and_parse(self):
        """Create METAR objects as we find products in the text"""
        # skip the top three lines
        lines = self.unixtext.split("\n")
        if lines[0] == "\001":
            content = "\n".join(lines[3:])
        elif len(lines[0]) < 5:
            content = "\n".join(lines[2:])
        else:
            self.warnings.append(
                ("WMO header split_and_parse fail: %s") % (self.unixtext,)
            )
            content = "\n".join(lines)
        # Tokenize on the '=', which splits a product with METARs
        tokens = content.split("=")
        for token in tokens:
            # Dump METARs that have NIL in them
            prefix = "METAR" if self.afos != "SPECI" else "SPECI"
            if NIL_RE.search(token):
                continue
            if token.find("METAR") > -1:
                token = token[(token.find("METAR") + 5) :]
            # unsure why this LWIS existed
            # elif token.find("LWIS ") > -1:
            #    token = token[token.find("LWIS ")+5:]
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
