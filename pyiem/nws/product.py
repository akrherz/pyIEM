'''
Created on Jan 5, 2013

@author: akrherz
'''
import datetime
import re
import sys

import pytz
from shapely.geometry import Polygon, MultiPolygon
from shapely.wkt import dumps

from pyiem import reference
from pyiem.nws import ugc, vtec, hvtec


AFOSRE = re.compile(r"^([A-Z0-9\s]{6})$", re.M)
TIME_RE = ("^([0-9]+) (AM|PM) ([A-Z][A-Z][A-Z]?T) ([A-Z][A-Z][A-Z]) "
           +"([A-Z][A-Z][A-Z]) ([0-9]+) ([1-2][0-9][0-9][0-9])$")
WMO_RE = re.compile(("^(?P<ttaaii>[A-Z0-9]{6}) (?P<cccc>[A-Z]{4}) "
                     +"(?P<ddhhmm>[0-3][0-9][0-2][0-9][0-5][0-9])\s*"
                     +"(?P<bbb>[ACR][ACOR][A-Z])?\s*$"), re.M)
TIME_MOT_LOC = re.compile((".*TIME\.\.\.MOT\.\.\.LOC (?P<ztime>[0-9]{4})Z "
                           +"(?P<dir>[0-9]{1,3})DEG (?P<sknt>[0-9]{1,3})KT "
                           +"(?P<loc>[0-9 ]+)"))
LAT_LON = re.compile("([0-9]{4,8})\s+")
WINDHAIL = re.compile((".*WIND\.\.\.HAIL (?P<winddir>[><]?)(?P<wind>[0-9]+)"
                       +"MPH (?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN"))
HAILTAG = re.compile(".*HAIL\.\.\.(?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN")
WINDTAG = re.compile(".*WIND\.\.\.(?P<winddir>[><]?)\s?(?P<wind>[0-9]+)\s?MPH")
TORNADOTAG = re.compile((".*TORNADO\.\.\.(?P<tornado>RADAR INDICATED|"
                         +"OBSERVED|POSSIBLE)"))
TORNADODAMAGETAG = re.compile((".*TORNADO DAMAGE THREAT\.\.\."
                        +"(?P<damage>CONSIDERABLE|SIGNIFICANT|CATASTROPHIC)"))
TORNADO = re.compile(r"^AT |^\* AT")

class TextProductException(Exception):
    """ throwable """
    pass

class TextProductSegment(object):
    """ A segment of a Text Product """
    
    def __init__(self, text, tp):
        """ Constructor """
        self.unixtext = text
        self.tp = tp # Reference to parent
        self.ugcs, self.ugcexpire = ugc.parse(text, tp.valid,
                                              ugc_provider=tp.ugc_provider)
        self.vtec = vtec.parse(text)
        self.headlines = self.parse_headlines()
        self.hvtec = hvtec.parse(text, nwsli_provider=tp.nwsli_provider)
        
        # TIME...MOT...LOC Stuff!
        self.tml_giswkt = None
        self.tml_valid = None
        self.tml_sknt = None
        self.tml_dir = None
        self.process_time_mot_loc()
        
        # 
        self.giswkt = None
        self.sbw = self.process_latlon()

        # tags
        self.windtag = None
        self.hailtag = None
        self.haildirtag = None
        self.winddirtag = None
        self.tornadotag = None
        self.tornadodamagetag = None
        self.process_tags()
        
        self.bullets = self.process_bullets()
    
    def get_hvtec_nwsli(self):
        """ Return the first hvtec NWSLI entry, if it exists """
        if len(self.hvtec) == 0:
            return None
        return self.hvtec[0].nwsli.id
    
    def svs_search(self):
        """ Special search the product for special text """
        sections = self.unixtext.split("\n\n")
        for s in sections:
            if len(TORNADO.findall(s)) > 0:
                return " ".join( s.replace("\n", " ").split() )
        return ""

        
    def process_bullets(self):
        """ Figure out the bulleted segments """
        parts = re.findall('^\*([^\*]*)', self.unixtext, re.M | re.DOTALL)
        bullets = []
        for part in parts:
            pos = part.find("\n\n")
            if pos > 0:
                bullets.append( " ".join(part[:pos].replace("\n", "").split()) )
            else:
                bullets.append( " ".join(part.replace("\n", "").split()) )
        return bullets
    
    def process_tags(self):
        """ Find various tags in this segment """
        nolf = self.unixtext.replace("\n", " ")
        m = WINDHAIL.match( nolf )
        if m:
            d = m.groupdict()
            self.windtag = d['wind']
            self.haildirtag = d['haildir']
            self.winddirtag = d['winddir']
            self.hailtag = d['hail']

        m = WINDTAG.match( nolf )
        if m:
            d = m.groupdict()
            self.winddirtag = d['winddir']
            self.windtag = d['wind']

        m = HAILTAG.match( nolf )
        if m:
            d = m.groupdict()
            self.haildirtag = d['haildir']
            self.hailtag = d['hail']

        m = TORNADOTAG.match( nolf )
        if m:
            d = m.groupdict()
            self.tornadotag = d['tornado']

        m = TORNADODAMAGETAG.match( nolf )
        if m:
            d = m.groupdict()
            self.tornadodamagetag = d['damage']

    def special_tags_to_text(self):
        """
        Convert the special tags into a nice text
        """
        if (self.windtag is None and self.tornadotag is None and
            self.hailtag is None and self.tornadodamagetag is None):
            return ""

        parts = []
        if self.tornadotag is not None:
            parts.append("tornado: %s" % (
                self.tornadotag  ))
        if self.tornadodamagetag is not None:
            parts.append("tornado damage threat: %s" % (
                self.tornadodamagetag  ))
        if self.windtag is not None:
            parts.append("wind: %s%s MPH" % (
                self.winddirtag.replace(">","&gt;").replace("<", "&lt;"),
                self.windtag))
        if self.hailtag is not None:
            parts.append("hail: %s%s IN" % (
                self.haildirtag.replace(">","&gt;").replace("<", "&lt;"),
                self.hailtag  ))
        return " ["+ ", ".join(parts) +"] "


    def process_latlon(self):
        """ FIND the LAT...LON data """
        data = self.unixtext.replace("\n", " ")
        pos = data.find("LAT...LON")
        if pos == -1:
            return None
        newdata = data[pos+9:]
        # Go find our next non-digit, non-space character, if we find it, we
        # should truncate our string, this could be improved, I suspect
        m = re.search(r"[^\s0-9]", newdata)
        if m is not None:
            pos2 = m.start()
            newdata = newdata[:pos2]

        pts = []
        partial = None
        def checker(lon, lat):
            ''' make sure our values are legit! '''
            if lat >= 90 or lat <= -90:
                raise TextProductException("invalid latitude %s from %s" % (
                                                        lat, newdata))
            if lon > 180 or lon < -180:
                raise TextProductException("invalid longitude %s from %s" % (
                                                        lon, newdata))
            return (lon, lat)
        
        # We have two potential formats, one with 4 or 5 places and one 
        # with eight!
        vals = re.findall(LAT_LON, newdata )
        for val in vals:
            if len(val) == 8:
                lat = float(val[:4]) / 100.00
                lon = float(val[4:]) / 100.00
                if lon < 40:
                    lon += 100.
                lon = 0 - lon
                pts.append( checker(lon, lat) )
            else:
                s = float(val) / 100.00
                if partial is None: # we have lat
                    partial = s 
                    continue
                # we have a lon
                if s < 40:
                    s += 100.
                s = 0 - s
                pts.append( checker(s, partial) )
                partial = None
        
        if len(pts) == 0:
            return None
        if pts[0][0] != pts[-1][0] and pts[0][1] != pts[-1][1]:
            pts.append( pts[0] )
        
        self.giswkt = 'SRID=4326;%s' % (dumps(MultiPolygon([ Polygon( pts ) ]),
                                              rounding_precision=6),)
        return Polygon( pts )

        
    def process_time_mot_loc(self):
        """ Try to parse the TIME...MOT...LOC """
        # TODO: The checking of time against self.ugcexpire is not perfect
        m = TIME_MOT_LOC.match( self.unixtext.replace("\n", " ") )
        if not m:
            return
        
        d = m.groupdict()
        if len(d['ztime']) != 4 or self.ugcexpire is None:
            return
        hh = int(d['ztime'][:2])
        mi = int(d['ztime'][2:])
        self.tml_valid = self.ugcexpire.replace(hour=hh, minute=mi)
        if hh > self.ugcexpire.hour:
            self.tml_valid = self.tml_valid - datetime.timedelta(days=1)

        self.tml_valid = self.tml_valid.replace(tzinfo=pytz.timezone('UTC'))

        tokens = d['loc'].split()
        lats = []
        lons = []
        if len(tokens) % 2 != 0:
            tokens = tokens[:-1]
        if len(tokens) == 0:
            return
        for i in range(0, len(tokens), 2):
            lats.append( float(tokens[i]) / 100.0 )
            lons.append( 0 - float(tokens[i+1]) / 100.0 )

        if len(lats) == 1:
            self.tml_giswkt = 'SRID=4326;POINT(%s %s)' % (lons[0], lats[0])
        else:
            pairs = []
            for lat, lon in zip(lats, lons):
                pairs.append( '%s %s' % (lon, lat) )
            self.tml_giswkt = 'SRID=4326;LINESTRING(%s)' % (','.join(pairs),)
        self.tml_sknt = int( d['sknt'] )
        self.tml_dir = int( d['dir'] )

    def parse_headlines(self):
        """ Find headlines in this segment """
        ar = re.findall("^\.\.\.(.*?)\.\.\.[ ]?\n\n", self.unixtext, 
                        re.M | re.S)
        for h in range(len(ar)):
            ar[h] = " ".join(ar[h].replace("...",", ").replace("\n", 
                                                               " ").split())
        return ar

    def get_affected_wfos(self):
        ''' Based on the ugc_provider, figure out which WFOs are impacted by
        this product segment '''
        affected_wfos = []
        for u in self.ugcs:
            for wfo in u.wfos:
                if wfo not in affected_wfos:
                    affected_wfos.append( wfo )
        
        return affected_wfos

class TextProduct(object):
    '''
    class representing a NWS Text Product
    '''


    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        '''
        Constructor
        @param text string single text product
        @param utcnow used to compute offsets for when this product my be valid
        @param ugc_provider a dictionary of UGC objects already setup
        '''
        self.warnings = []
        
        self.text = text
        if ugc_provider is None:
            ugc_provider = {}
        if nwsli_provider is None:
            nwsli_provider = {}
        self.ugc_provider = ugc_provider
        self.nwsli_provider = nwsli_provider
        self.unixtext = text.replace("\r\r\n", "\n")
        self.sections = self.unixtext.split("\n\n")
        self.afos = None
        self.valid = None
        self.source = None
        self.wmo = None
        self.ddhhmm = None
        self.bbb = None
        self.utcnow = utcnow
        self.segments = []
        self.z = None
        self.tz = None
        self.geometry = None
        if utcnow is None:
            utc = datetime.datetime.utcnow()
            self.utcnow = utc.replace(tzinfo=pytz.timezone('UTC'))
        
        self.parse_wmo()
        self.parse_afos()
        self.parse_valid()
        self.parse_segments()
    
    def is_resent(self):
        """ Check to see if this product is a ...RESENT product """
        return (self.unixtext.find("...RESENT") > 0)

    def is_correction(self):
        """Returns boolean on if this product is some form of correction """
        return self.bbb is not None
        
    def get_channels(self):
        """ Return a list of channels """
        return [self.afos,]
        
    def get_jabbers(self, uri, uri2=None):
        ''' Return a list of triples representing what we should send to 
        our precious jabber routing bot, this should be overridden by the
        specialty parsers '''
        res = []
        url = "%s?pid=%s" % (uri, self.get_product_id())
        plain = "%s issues %s %s" % (self.source[1:], 
                    reference.prodDefinitions.get(self.afos[:3], 
                                                  self.afos[:3]), url)
        html = '<p>%s issues <a href="%s">%s</a></p>' % (self.source[1:], url,
                    reference.prodDefinitions.get(self.afos[:3], 
                                                  self.afos[:3]))
        xtra = {
                'channels': ",".join( self.get_channels() ),
                'product_id': self.get_product_id(),
                'twitter': plain
                }
        res.append( (plain, html, xtra))
        return res
        
    def get_signature(self):
        """ Find the signature at the bottom of the page 
        """
        return " ".join(self.segments[-1].unixtext.replace("\n", 
                                                      " ").strip().split())
        
    def parse_segments(self):
        """ Split the product by its && """
        segs = self.unixtext.split("$$")
        for s in segs:
            self.segments.append(TextProductSegment(s, self))

    
    def get_product_id(self):
        """ Get an identifier of this product used by the IEM """
        s = "%s-%s-%s-%s" % (self.valid.strftime("%Y%m%d%H%M"),
                self.source, self.wmo, self.afos)
        return s.strip()

    
    def parse_valid(self):
        """ Figre out the valid time of this product """
        # Now lets look for a local timestamp in the product MND or elsewhere
        tokens = re.findall(TIME_RE, self.unixtext, re.M)
        # If we don't find anything, lets default to now, its the best
        if len(tokens) > 0:
            # [('1249', 'AM', 'EDT', 'JUL', '1', '2005')]
            self.z = tokens[0][2]
            self.tz = pytz.timezone( reference.name2pytz.get(self.z, 'UTC') )
            if len(tokens[0][0]) < 3:
                h = tokens[0][0]
                m = 0
            else:
                h = tokens[0][0][:-2]
                m = tokens[0][0][-2:]
            dstr = "%s:%s %s %s %s %s" % (h, m, tokens[0][1], tokens[0][4], 
                                      tokens[0][5], tokens[0][6])
            # Careful here, need to go to UTC time first then come back!
            try:
                now = datetime.datetime.strptime(dstr, "%I:%M %p %b %d %Y")
            except ValueError:
                msg = ("Invalid timestamp [%s] found in product "
                       +"[%s %s %s] header") % (" ".join(tokens[0]), self.wmo, 
                                                self.source, self.afos)
                sys.exc_clear()
                raise TextProductException(self.source[1:], msg)
            now += datetime.timedelta(hours= reference.offsets[self.z])
            self.valid = now.replace(tzinfo=pytz.timezone('UTC'))
            return
        # Search out the WMO header, this had better always be there
        # We only care about the first hit in the file, searching from top
        
        # Take the first hit, ignore others
        wmo_day = int(self.ddhhmm[:2])
        wmo_hour = int(self.ddhhmm[2:4])
        wmo_minute = int(self.ddhhmm[4:])

        self.valid = self.utcnow.replace(hour=wmo_hour, minute=wmo_minute,
                                         second=0, microsecond=0)
        if wmo_day == self.utcnow.day:
            return
        elif wmo_day - self.utcnow.day == 1: # Tomorrow
            self.valid = self.valid.replace(day=wmo_day)
        elif wmo_day > 25 and self.utcnow.day < 5: # Previous month!
            self.valid = self.valid + datetime.timedelta(days=-10)
            self.valid = self.valid.replace(day=wmo_day)
        elif wmo_day < 5 and self.utcnow.day > 25: # next month
            self.valid = self.valid + datetime.timedelta(days=10)
            self.valid = self.valid.replace(day=wmo_day)
        else:
            self.valid = self.valid.replace(day=wmo_day)

    def parse_wmo(self):
        """ Parse things related to the WMO header"""
        m = WMO_RE.search( self.unixtext[:100] )
        if m is None:
            raise TextProductException(("FATAL: Could not parse WMO header! "
                                        +"%s") % (self.text[:100]))
        d = m.groupdict()
        self.wmo = d['ttaaii']
        self.source = d['cccc']
        self.ddhhmm = d['ddhhmm']
        self.bbb = d['bbb']

    def get_affected_wfos(self):
        ''' Based on the ugc_provider, figure out which WFOs are impacted by
        this product '''
        affected_wfos = []
        for segment in self.segments:
            for u in segment.ugcs:
                for wfo in u.wfos:
                    if wfo not in affected_wfos:
                        affected_wfos.append( wfo )
        
        return affected_wfos
    
    def parse_afos(self):
        """ Figure out what the AFOS PIL is """
        data = "\n".join([line.strip()
                         for line in self.sections[0].split("\n")])
        tokens = re.findall("^([A-Z0-9 ]{4,6})$", data, re.M)
        if len(tokens) > 0:
            self.afos = tokens[0]

