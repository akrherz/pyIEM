'''
Created on Jan 5, 2013

@author: akrherz
'''
import datetime
import re

import pytz
from shapely.geometry import Polygon, MultiPolygon

from pyiem import reference
from pyiem.nws import ugc, vtec, hvtec

AFOSRE = re.compile(r"^([A-Z0-9\s]{6})$", re.M)
TIME_RE = "^([0-9]+) (AM|PM) ([A-Z][A-Z][A-Z]?T) [A-Z][A-Z][A-Z] ([A-Z][A-Z][A-Z]) ([0-9]+) ([1-2][0-9][0-9][0-9])$"
WMO_RE = "^[A-Z0-9]{6} [A-Z]{4} ([0-3][0-9])([0-2][0-9])([0-5][0-9])"
TIME_MOT_LOC = re.compile(".*TIME\.\.\.MOT\.\.\.LOC (?P<ztime>[0-9]{4})Z (?P<dir>[0-9]{1,3})DEG (?P<sknt>[0-9]{1,3})KT (?P<loc>[0-9 ]+)")
LAT_LON = re.compile("([0-9]+)\s+([0-9]+)")
WINDHAIL = re.compile(".*WIND\.\.\.HAIL (?P<winddir>[><]?)(?P<wind>[0-9]+)MPH (?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN")
HAILTAG = re.compile(".*HAIL\.\.\.(?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN")
WINDTAG = re.compile(".*WIND\.\.\.(?P<winddir>[><]?)\s?(?P<wind>[0-9]+)\s?MPH")
TORNADOTAG = re.compile(".*TORNADO\.\.\.(?P<tornado>RADAR INDICATED|OBSERVED|POSSIBLE)")
TORNADODAMAGETAG = re.compile(".*TORNADO DAMAGE THREAT\.\.\.(?P<damage>SIGNIFICANT|CATASTROPHIC)")
TORNADO = re.compile(r"^AT |^\* AT")

class TextProductException(Exception):
    ''' throwable '''
    pass

class TextProductSegment(object):
    
    def __init__(self, text, tp):
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


    def process_latlon(self):
        """ FIND the LAT...LON data """
        data = self.unixtext.replace("\n", " ")
        pos = data.find("LAT...LON")
        if pos == -1:
            return None
        newdata = data[pos+9:]
        m = re.search(r"[^ 0-9]", newdata)
        if m is not None:
            pos2 = m.start()
            newdata = newdata[:pos2]
        pairs = re.findall(LAT_LON, newdata )
        if len(pairs) == 0:
            return None
        pts = []
        for pr in pairs:
            lat = float(pr[0]) / 100.00
            lon = 0 - float(pr[1]) / 100.00
            pts.append( (lon, lat) )
        pts.append( pts[0] )
        
        self.giswkt = 'SRID=4326;%s' % (MultiPolygon([ Polygon( pts ) ]).wkt,)
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
        for i in range(0,len(tokens),2):
            lats.append( float(tokens[i]) / 100.0 )
            lons.append( 0 - float(tokens[i+1]) / 100.0 )

        if len(lats) == 1:
            self.tml_giswkt = 'SRID=4326;POINT(%s %s)' % (lons[0], lats[0])
        else:
            pairs = []
            for lat,lon in zip(lats,lons):
                pairs.append( '%s %s' % (lon, lat) )
            self.tml_giswkt = 'SRID=4326;LINESTRING(%s)' % (','.join(pairs),)
        self.tml_sknt = int( d['sknt'] )
        self.tml_dir = int( d['dir'] )

    def parse_headlines(self):
        """ Find headlines in this segment """
        ar = re.findall("^\.\.\.(.*?)\.\.\.[ ]?\n\n", self.unixtext, 
                        re.M | re.S)
        for h in range(len(ar)):
            ar[h] = " ".join(ar[h].replace("...",", ").replace("\n", " ").split())
        return ar

class TextProduct(object):
    '''
    class representing a NWS Text Product
    '''


    def __init__(self, text, utcnow=None, ugc_provider={},
                 nwsli_provider={}):
        '''
        Constructor
        @param text string single text product
        @param utcnow used to compute offsets for when this product my be valid
        @param ugc_provider a dictionary of UGC objects already setup
        '''
        self.warnings = []
        
        self.text = text
        self.ugc_provider = ugc_provider
        self.nwsli_provider = nwsli_provider
        self.unixtext = text.replace("\r\r\n", "\n")
        self.sections = self.unixtext.split("\n\n")
        self.afos = None
        self.valid = None
        self.source = None
        self.wmo = None
        self.utcnow = utcnow
        self.segments = []
        self.z = None
        self.tz = None
        if utcnow is None:
            utc = datetime.datetime.utcnow()
            self.utcnow = utc.replace(tzinfo=pytz.timezone('UTC'))
        
        self.parse_afos()
        self.parse_valid()
        self.parse_wmo()
        self.parse_segments()
        
    def get_jabbers(self, uri):
        ''' Return a list of triples representing what we should send to 
        our precious jabber routing bot, this should be overridden by the
        specialty parsers '''
        res = []
        url = "%s%s" % (uri, self.get_product_id())
        plain = "%s issues %s %s" % (self.source[1:], 
                    reference.prodDefinitions.get(self.afos[:3], 
                                                  self.afos[:3]), url)
        html = '<p>%s issues <a href="%s">%s</a></p>' % (self.source[1:], url,
                    reference.prodDefinitions.get(self.afos[:3], 
                                                  self.afos[:3]))
        xtra = {
                'channels': self.afos,
                'product_id': self.get_product_id(),
                'tweet': plain
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
            dstr = "%s:%s %s %s %s %s" % (h, m, tokens[0][1], tokens[0][3], 
                                      tokens[0][4], tokens[0][5])
            ''' Careful here, need to go to UTC time first then come back! '''
            now = datetime.datetime.strptime(dstr, "%I:%M %p %b %d %Y")
            now += datetime.timedelta(hours= reference.offsets[self.z])
            self.valid = now.replace(tzinfo=pytz.timezone('UTC'))
            return
        # Search out the WMO header, this had better always be there
        # We only care about the first hit in the file, searching from top
        
        tokens = re.findall(WMO_RE, self.unixtext[:100], re.M)
        if len(tokens) == 0:
            raise TextProductException("FATAL: Could not find WMO Header timestamp, bad!")
        # Take the first hit, ignore others
        wmo_day = int(tokens[0][0])
        wmo_hour = int(tokens[0][1])
        wmo_minute = int(tokens[0][2])

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
        t = re.findall("^([A-Z]{4}[0-9][0-9]) ([A-Z]{4})", self.sections[0], 
                       re.M)
        if len(t) > 0:
            self.wmo = t[0][0]
            self.source = t[0][1]

    
    def parse_afos(self):
        """ Figure out what the AFOS PIL is """
        data = "\n".join([line.strip()
                         for line in self.sections[0].split("\n")])
        tokens = re.findall("^([A-Z0-9 ]{4,6})$", data, re.M)
        if len(tokens) > 0:
            self.afos = tokens[0]

class SPSProduct(TextProduct):
    ''' class for Special Weather Statements '''
    
    def __init__(self, text):
        ''' constructor '''
        self.geometry = None
        TextProduct.__init(self, text)

def parser( text ):
    ''' generalized parser of a text product '''
    tokens = AFOSRE.findall(text[:100].replace('\r\r\n', '\n'))
    if len(tokens) == 0:
        raise TextProductException("Could not locate AFOS Identifier")
    afos = tokens[0][:3]
    if afos == 'SPS':
        return SPSProduct( text )
    elif afos == 'CLI':
        from pyiem.nws.products.cli import parser as cliparser
        return cliparser( text )
    
    return TextProduct( text )