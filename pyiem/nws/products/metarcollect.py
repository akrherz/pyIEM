"""Encapsulates a text product holding METARs

The source of the metar library is
18 Jul 2017: `snowdepth` branch of my python-metar fork installed with pip
"""
from __future__ import print_function
import re
import datetime

import pytz
from pyiem.nws.product import TextProduct
from pyiem.observation import Observation
from pyiem import datatypes
from pyiem.util import drct2text
from metar.Metar import Metar
from metar.Metar import ParserError as MetarParserError

NIL_RE = re.compile(r"[\s\n]NIL")
ERROR_RE = re.compile("Unparsed groups in body '(?P<msg>.*)' while processing")
TORNADO_RE = re.compile(r" \+FC |TORNADO")
FUNNEL_RE = re.compile(r" FC |FUNNEL")
# Sites we should route to Jabber
JABBER_SITES = {}
# Keep track of Wind alerts to prevent dups
WIND_ALERTS = {}
# Wind speed threshold in kts for alerting
WIND_ALERT_THRESHOLD_KTS = 50.


def to_metar(textprod, text):
    """Create a METAR object, if possible"""
    # Do some cleaning and whitespace trimming
    text = sanitize(text)
    if len(text) < 10:
        return
    attempt = 1
    mtr = None
    original_text = text
    while attempt < 6 and mtr is None:
        try:
            mtr = METARReport(text, month=textprod.valid.month,
                              year=textprod.valid.year)
        except MetarParserError as inst:
            tokens = ERROR_RE.findall(str(inst))
            if tokens:
                if tokens[0] == text or text.startswith(tokens[0]):
                    print(("%s Aborting due to non-replace %s"
                           ) % (textprod.get_product_id(), str(inst)))
                    return
                # So tokens contains a series of groups that needs updated
                newtext = text
                for token in tokens[0].split():
                    newtext = newtext.replace(" %s" % (token, ), "")
                if newtext != text:
                    text = newtext
                else:
                    print("unparsed groups regex fail: %s" % (inst, ))

    if mtr is not None:
        # Attempt to figure out more things
        if mtr.station_id is None:
            print("Aborting due to station_id being None |%s|" % (text, ))
            return None
        if mtr.time is None:
            print("Aborting due to time being None |%s|" % (text, ))
            return None
        # don't allow data more than an hour into the future
        utcnow = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        if utcnow < mtr.time:
            print(("Aborting due to time in the future "
                   "utcnow: %s mtr.time: %s"
                   ) % (utcnow, mtr.time))
            return None
        mtr.code = original_text
        mtr.iemid = (mtr.station_id[-3:]
                     if mtr.station_id[0] == 'K'
                     else mtr.station_id)
        mtr.network = textprod.nwsli_provider.get(mtr.iemid,
                                                  dict()).get('network')
    return mtr


def sanitize(text):
    """Clean our text string with METAR data
    """
    text = re.sub("\015", " ", text)
    # Remove any multiple whitespace, bad chars
    text = text.encode('latin-1'
                       ).replace('\xa0', " "
                                 ).replace("\001", ""
                                           ).replace("\003", ""
                                                     ).replace("COR ", "")
    text = " ".join(text.strip().split())
    # Look to see that our METAR starts with A-Z
    if re.match("^[0-9]", text):
        tokens = text.split()
        text = " ".join(tokens[1:])
    return text


class METARReport(Metar):
    """Provide some additional functionality over baseline METAR"""

    def __init__(self, text, **kwargs):
        """Wrapper"""
        Metar.__init__(self, text, **kwargs)
        self.iemid = None
        self.network = None

    def wind_message(self):
        """Convert this into a Jabber style message"""
        drct = 0
        sknt = 0
        if self.wind_gust:
            sknt = self.wind_gust.value("KT")
            if self.wind_dir:
                drct = self.wind_dir.value()
            time = self.time.replace(tzinfo=pytz.utc)
        if self.wind_speed_peak:
            v1 = self.wind_speed_peak.value("KT")
            d1 = self.wind_dir_peak.value()
            t1 = self.peak_wind_time.replace(tzinfo=pytz.utc)
            if v1 > sknt:
                sknt = v1
                drct = d1
                time = t1
        key = "%s;%s;%s" % (self.station_id, sknt, time)
        if key not in WIND_ALERTS:
            WIND_ALERTS[key] = 1
            speed = datatypes.speed(sknt, 'KT')
            return ("gust of %.0f knots (%.1f mph) from %s @ %s"
                    ) % (speed.value('KT'), speed.value('MPH'),
                         drct2text(drct), time.strftime("%H%MZ"))

    def over_wind_threshold(self):
        """Is this METAR over the wind threshold for alerting"""
        if (self.wind_gust and
                self.wind_gust.value("KT") >= WIND_ALERT_THRESHOLD_KTS):
            return True
        if (self.wind_speed_peak and
                self.wind_speed_peak.value("KT") >= WIND_ALERT_THRESHOLD_KTS):
            return True
        return False

    def to_iemaccess(self, txn):
        """Persist this data object to IEMAccess"""
        gts = self.time.replace(tzinfo=pytz.timezone("UTC"))
        iem = Observation(self.iemid, self.network, gts)
        # Load the observation from the database, if the same time exists!
        iem.load(txn)

        # Need to figure out if we have a duplicate ob, if so, check
        # the length of the raw data, if greater, take the temps
        if (iem.data['raw'] is not None and
                len(iem.data['raw']) >= len(self.code)):
            pass
        else:
            if self.temp:
                val = self.temp.value("F")
                # Place reasonable bounds on the temperature before saving it!
                if val > -90 and val < 150:
                    iem.data['tmpf'] = round(val, 1)
            if self.dewpt:
                iem.data['dwpf'] = round(self.dewpt.value("F"), 1)
            # Daabase only allows len 254
            iem.data['raw'] = self.code[:254]

        if self.wind_speed:
            iem.data['sknt'] = self.wind_speed.value("KT")
        if self.wind_gust:
            iem.data['gust'] = self.wind_gust.value("KT")
        if self.wind_dir:
            if self.wind_dir.value() == 'VRB':
                iem.data['drct'] = 0
            else:
                iem.data['drct'] = float(self.wind_dir.value())

        if not self.wind_speed_peak:
            old_max_wind = max([iem.data.get('max_sknt', 0),
                                iem.data.get('max_gust', 0)])
            new_max_wind = max([iem.data.get('sknt', 0),
                                iem.data.get('gust', 0)])
            if new_max_wind > old_max_wind:
                # print 'Setting max_drct manually: %s' % (clean_metar,)
                iem.data['max_drct'] = iem.data.get('drct', 0)

        if self.wind_speed_peak:
            iem.data['max_gust'] = self.wind_speed_peak.value("KT")
        if self.wind_dir_peak:
            iem.data['max_drct'] = self.wind_dir_peak.value()
        if self.peak_wind_time:
            iem.data['max_gust_ts'] = self.peak_wind_time.replace(
                tzinfo=pytz.timezone("UTC"))

        if self.max_temp_6hr:
            iem.data['max_tmpf_6hr'] = round(self.max_temp_6hr.value("F"), 1)
            if iem.data['valid'].hour >= 6:
                iem.data['max_tmpf'] = round(self.max_temp_6hr.value("F"), 1)
        if self.min_temp_6hr:
            iem.data['min_tmpf_6hr'] = round(self.min_temp_6hr.value("F"), 1)
            if iem.data['valid'].hour >= 6:
                iem.data['min_tmpf'] = round(self.min_temp_6hr.value("F"), 1)
        if self.max_temp_24hr:
            iem.data['max_tmpf_24hr'] = round(self.max_temp_24hr.value("F"), 1)
        if self.min_temp_24hr:
            iem.data['min_tmpf_24hr'] = round(self.min_temp_24hr.value("F"), 1)
        if self.precip_3hr:
            iem.data['p03i'] = self.precip_3hr.value("IN")
        if self.precip_6hr:
            iem.data['p06i'] = self.precip_6hr.value("IN")
        if self.precip_24hr:
            iem.data['p24i'] = self.precip_24hr.value("IN")

        if self.snowdepth:
            iem.data['snowd'] = self.snowdepth.value("IN")
        if self.vis:
            iem.data['vsby'] = self.vis.value("SM")
        if self.press:
            iem.data['alti'] = self.press.value("IN")
        if self.press_sea_level:
            iem.data['mslp'] = self.press_sea_level.value("MB")
        if self.press_sea_level and self.press:
            alti = self.press.value("MB")
            mslp = self.press_sea_level.value("MB")
            if abs(alti - mslp) > 25:
                print(("PRESSURE ERROR %s %s ALTI: %s MSLP: %s"
                       ) % (iem.data['station'], iem.data['valid'],
                            alti, mslp))
                if alti > mslp:
                    iem.data['mslp'] += 100.
                else:
                    iem.data['mslp'] -= 100.
        iem.data['phour'] = 0
        if self.precip_1hr:
            iem.data['phour'] = self.precip_1hr.value("IN")
        # Do something with sky coverage
        for i in range(len(self.sky)):
            (cov, hgh, _) = self.sky[i]
            iem.data['skyc%s' % (i+1)] = cov
            if hgh is not None:
                iem.data['skyl%s' % (i+1)] = hgh.value("FT")

        # Presentwx
        if self.weather:
            pwx = []
            for wx in self.weather:
                pwx.append(("").join([a for a in wx if a is not None]))
            iem.data['presentwx'] = (",".join(pwx))[:24]

        return iem, iem.save(txn)


class METARCollective(TextProduct):
    """
    A TextProduct containing METAR information
    """

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        """Constructor

        Args:
          text (string): the raw string to process"""
        TextProduct.__init__(self, text, utcnow, ugc_provider,
                             nwsli_provider)
        self.metars = []
        self.split_and_parse()

    def get_jabbers(self, uri=None, uri2=None):
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
                    channels = ["METAR.%s" % (mtr.station_id, )]
                    if mtr.type == 'SPECI':
                        channels.append("SPECI.%s" % (mtr.station_id, ))
                    mstr = "%s %s" % (mtr.type, mtr.code)
                    jmsgs.append([mstr, mstr,
                                  dict(channels=",".join(channels))])
            if msg:
                row = self.nwsli_provider.get(mtr.iemid, dict())
                wfo = row.get('wfo')
                if wfo is None or wfo == '':
                    print(("Unknown WFO for id: %s, skipping alert"
                           ) % (mtr.iemid,))
                    continue
                channels = ["METAR.%s" % (mtr.station_id, )]
                if mtr.type == 'SPECI':
                    channels.append("SPECI.%s" % (mtr.station_id, ))
                channels.append(wfo)
                st = row.get('state')
                nm = row.get('name')

                extra = ""
                if mtr.code.find("$") > 0:
                    extra = "(Caution: Maintenance Check Indicator)"
                url = ("%s%s") % (uri, mtr.network)
                jtxt = ("%s,%s (%s) ASOS %s reports %s\n%s %s"
                        ) % (nm, st, mtr.iemid, extra, msg, mtr.code, url)
                xtra = {'channels': ",".join(channels),
                        'lat':  str(row.get('lat')),
                        'long': str(row.get('lon'))}
                xtra['twitter'] = ("%s,%s (%s) ASOS reports %s"
                                   ) % (nm, st, mtr.iemid, msg)
                jmsgs.append([jtxt, jtxt, xtra])

        return jmsgs

    def split_and_parse(self):
        """Create METAR objects as we find products in the text"""
        # skip the top three lines
        lines = self.unixtext.split("\n")
        if lines[0] == '\001':
            content = "\n".join(lines[3:])
        elif len(lines[0]) < 5:
            content = "\n".join(lines[2:])
        else:
            self.warnings.append(("WMO header split_and_parse fail: %s"
                                  ) % (self.unixtext, ))
            content = "\n".join(lines)
        # Tokenize on the '=', which splits a product with METARs
        tokens = content.split("=")
        for token in tokens:
            # Dump METARs that have NIL in them
            prefix = "METAR" if self.afos != 'SPECI' else 'SPECI'
            if NIL_RE.search(token):
                continue
            elif token.find("METAR") > -1:
                token = token[token.find("METAR")+5:]
            # unsure why this LWIS existed
            # elif token.find("LWIS ") > -1:
            #    token = token[token.find("LWIS ")+5:]
            elif token.find("SPECI") > -1:
                token = token[token.find("SPECI")+5:]
                prefix = 'SPECI'
            elif len(token.strip()) < 5:
                continue
            res = to_metar(self, token)
            if res:
                res.type = prefix
                self.metars.append(res)


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function '''
    return METARCollective(text, utcnow, ugc_provider, nwsli_provider)
