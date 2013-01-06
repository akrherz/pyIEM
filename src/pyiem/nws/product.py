'''
Created on Jan 5, 2013

@author: akrherz
'''
import datetime
import re

from pyiem import iemtz, reference
from pyiem.nws import ugc, vtec, hvtec

TIME_RE = "^([0-9]+) (AM|PM) ([A-Z][A-Z][A-Z]?T) [A-Z][A-Z][A-Z] ([A-Z][A-Z][A-Z]) ([0-9]+) ([1-2][0-9][0-9][0-9])$"
WMO_RE = "^[A-Z0-9]{6} [A-Z]{4} ([0-3][0-9])([0-2][0-9])([0-5][0-9])"
TIME_MOT_LOC = re.compile(".*TIME\.\.\.MOT\.\.\.LOC (?P<ztime>[0-9]{4})Z (?P<dir>[0-9]{1,3})DEG (?P<sknt>[0-9]{1,3})KT (?P<loc>[0-9 ]+)")
LAT_LON = re.compile("([0-9]+)\s+([0-9]+)")
WINDHAIL = re.compile(".*WIND\.\.\.HAIL (?P<winddir>[><]?)(?P<wind>[0-9]+)MPH (?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN")
HAILTAG = re.compile(".*HAIL\.\.\.(?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN")
WINDTAG = re.compile(".*WIND\.\.\.(?P<winddir>[><]?)\s?(?P<wind>[0-9]+)\s?MPH")
TORNADOTAG = re.compile(".*TORNADO\.\.\.(?P<tornado>RADAR INDICATED|OBSERVED|POSSIBLE)")
TORNADODAMAGETAG = re.compile(".*TORNADO DAMAGE THREAT\.\.\.(?P<damage>SIGNIFICANT|CATASTROPHIC)")

class TextProductSegment(object):
    
    def __init__(self, text, tp):
        self.unixtext = text
        self.tp = tp # Reference to parent
        self.ugcs, self.ugcexpire = ugc.parse(text, tp.valid)
        self.vtec = vtec.parse(text)
        self.headlines = self.parse_headlines()
        self.hvtec = hvtec.parse(text)
        
        # TIME...MOT...LOC Stuff!
        self.tml_giswkt = None
        self.tml_valid = None
        self.tml_sknt = None
        self.tml_dir = None
        self.process_time_mot_loc()
        
        # segment GISWKT
        self.giswkt = None
        self.process_latlon()

        # tags
        self.windtag = None
        self.hailtag = None
        self.haildirtag = None
        self.winddirtag = None
        self.tornadotag = None
        self.tornadodamagetag = None
        self.process_tags()
        
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
            return
        newdata = data[pos+9:]
        pos2 = re.search(r"[^ 0-9]", newdata).start()
        pairs = re.findall(LAT_LON, newdata[:pos2] )
        if len(pairs) == 0:
            return
        g = "SRID=4326;MULTIPOLYGON((("
        for pr in pairs:
            lat = float(pr[0]) / 100.00
            lon = float(pr[1]) / 100.00
            g += "-%s %s," % (lon, lat)
        g += "-%s %s" % ( float(pairs[0][1]) / 100.00, float(pairs[0][0]) / 100.00)
        g += ")))"
        self.giswkt = g

        
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

        self.tml_valid = self.tml_valid.replace(tzinfo=iemtz.UTC())

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


    def __init__(self, text, utcnow=None):
        '''
        Constructor
        @param text string single text product
        @param utcnow used to compute offsets for when this product my be valid
        '''
        self.text = text
        self.unixtext = text.replace("\r\r\n", "\n")
        self.sections = self.unixtext.split("\n\n")
        self.afos = None
        self.valid = None
        self.source = None
        self.wmo = None
        self.utcnow = utcnow
        self.segments = []
        if utcnow is None:
            utc = datetime.datetime.utcnow()
            self.utcnow = utc.replace(tzinfo=iemtz.UTC())
        
        self.parse_afos()
        self.parse_valid()
        self.parse_wmo()
        self.parse_segments()
        
    def parse_segments(self):
        """ Split the product by its && """
        segs = self.unixtext.split("$$")
        for s in segs:
            self.segments.append(TextProductSegment(s, self))

    
    def get_product_id(self):
        """ Get an identifier of this product used by the IEM """
        s = "%s-%s-%s-%s" % (self.issueTime.strftime("%Y%m%d%H%M"),
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
            if len(tokens[0][0]) < 3:
                h = tokens[0][0]
                m = 0
            else:
                h = tokens[0][0][:-2]
                m = tokens[0][0][-2:]
            dstr = "%s:%s %s %s %s %s" % (h, m, tokens[0][1], tokens[0][3], 
                                      tokens[0][4], tokens[0][5])
            now = datetime.datetime.strptime(dstr, "%I:%M %p %b %d %Y")
            offset = reference.offsets.get(self.z)
            if offset is not None:
                now =  now + datetime.timedelta(
                                        hours=offset)
                self.valid = now.replace(tzinfo=iemtz.UTC())
                return
            else:
                print "Unknown TZ: %s " % (self.z,)

        # Search out the WMO header, this had better always be there
        # We only care about the first hit in the file, searching from top
        
        tokens = re.findall(WMO_RE, self.unixtext[:100], re.M)
        if len(tokens) == 0:
            print "FATAL: Could not find WMO Header timestamp, bad!"
            return
        # Take the first hit, ignore others
        wmo_day = int(tokens[0][0])
        wmo_hour = int(tokens[0][1])
        wmo_minute = int(tokens[0][2])

        self.valid = self.utcnow.replace(hour=wmo_hour,minute=wmo_minute)
        if wmo_day == self.utcnow.day:
            return
        elif wmo_day - self.utcnow.day == 1: # Tomorrow
            self.valid = self.utcnow.replace(day=wmo_day)
            return
        elif wmo_day > 25 and self.utcnow.day < 5: # Previous month!
            self.valid = self.utcnow + datetime.timedelta(days=-10)
            self.valid = self.valid.replace(day=wmo_day)
            return
        elif wmo_day < 5 and self.utcnow.day > 25: # next month
            self.valid = self.utcnow + datetime.timedelta(days=10)
            self.valid = self.valid.replace(day=wmo_day)
            return
        
        # IF we made it here, we are in trouble
        print 'findvalid ERROR: gmtnow: %s wmo: D:%s H:%s M:%s' % (
                        self.utcnow, wmo_day, wmo_hour, wmo_minute)

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
