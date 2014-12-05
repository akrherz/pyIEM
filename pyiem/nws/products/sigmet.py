""" Parse SIGMETs """
# Stdlib imports
import re
import datetime
import math

# Third Party
from shapely.geometry import Polygon, Point

# Local stuff
from pyiem.nws.product import TextProduct

O_LINE1 = re.compile("SIGMET (?P<name>[A-Z]*) (?P<num>[0-9]*) VALID (?P<sts>[0-9]{6})/(?P<ets>[0-9]{6})")
O_PAIRS = re.compile("(?P<lat>[NS][0-9]{4}) (?P<lon>[EW][0-9]{5})")
CS_RE = re.compile(r"""CONVECTIVE\sSIGMET\s(?P<label>[0-9A-Z]+)\s
VALID\sUNTIL\s(?P<hour>[0-2][0-9])(?P<minute>[0-5][0-9])Z\s
(?P<states>[A-Z ]+)\s
(?P<from>FROM)\s?(?P<locs>[0-9A-Z \-]+?)\s
(?P<dmshg>DMSHG|DVLPG|INTSF)?\s?(?P<geotype>AREA|LINE|ISOL)?\s?
(?P<cutype>EMBD|SEV|SEV\sEMBD|EMBD\sSEV)?\s?TS\s(?P<width>[0-9]+\sNM\sWIDE)?(?P<diameter>D[0-9]+)?
""", re.VERBOSE )

FROM_RE = re.compile(r"""
(?P<offset>[0-9]+)?(?P<drct>N|NE|NNE|ENE|E|ESE|SE|SSE|S|SSW|SW|WSW|W|WNW|NW|NNW)?\s?(?P<loc>[A-Z0-9]{3})
""", re.VERBOSE)

OL_RE = re.compile(r"""
OUTLOOK\sVALID\s(?P<begin>[0-9]{6})-(?P<end>[0-9]{6})\n
""", re.VERBOSE)

AREA_RE = re.compile(r"""
AREA\s(?P<areanum>[0-9]+)\.\.\.FROM\s(?P<locs>[0-9A-Z \-]+)\n
""", re.VERBOSE)

LINE_RE = re.compile(r"""
(?P<distance>[0-9]*)NM\s+EITHER\s+SIDE\s+OF\s+LINE\s+
""", re.VERBOSE)

CIRCLE_RE = re.compile(r"""
WI\s+(?P<distance>[0-9]*)NM\s+OF\s+
""", re.VERBOSE)


dirs = {'NNE': 22.5, 'ENE': 67.5, 'NE':  45.0, 'E': 90.0, 'ESE': 112.5,
        'SSE': 157.5, 'SE': 135.0, 'S': 180.0, 'SSW': 202.5,
        'WSW': 247.5, 'SW': 225.0, 'W': 270.0, 'WNW': 292.5,
        'NW': 315.0, 'NNW': 337.5, 'N': 0, '': 0}

KM_SM = 1.609347

class SIGMET(object):
    
    def __init__(self):
        """ Constructor """
        self.sts = None
        self.ets = None
        self.geom = None
        self.label = None
        self.areatext = ""
        self.centers = []
        self.raw = None

class SIGMETException(Exception):
    ''' Exception '''
    pass

def figure_expire(ptime, hour, minute):
    """
    Convert something like 0255Z into a full blown time
    """
    expire = ptime
    if hour < ptime.hour:
        expire += datetime.timedelta(days=1)
    return expire.replace(hour=hour,minute=minute)

def go2lonlat(lon0, lat0, direction, displacement):
    # http://stackoverflow.com/questions/7222382
    R = 6378.1 #Radius of the Earth
    brng = math.radians(dirs[direction]) #Bearing is 90 degrees converted to radians.
    d = displacement / KM_SM #Distance in km

    lat1 = math.radians(lat0) #Current lat point converted to radians
    lon1 = math.radians(lon0) #Current long point converted to radians

    lat2 = math.asin( math.sin(lat1)*math.cos(d/R) +
                       math.cos(lat1)*math.sin(d/R)*math.cos(brng))

    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1),
             math.cos(d/R)-math.sin(lat1)*math.sin(lat2))

    lat2 = math.degrees(lat2)
    lon2 = math.degrees(lon2)

    return lon2, lat2

def locs2lonslats(loc_provider, locstr, geotype, widthstr, diameterstr):
    """
    Convert a locstring into a lon lat arrays
    """
    lats = []
    lons = []
    #if geotype == 'LINE':
    #    width = float(widthstr.replace(" NM WIDE", ""))
        # Approximation
    #    widthdeg = width / 110.

    #print "locstr is:%s geotype is:%s" % (locstr, geotype)
    for l in locstr.split('-'):
        s = FROM_RE.search(l)
        if s:
            d = s.groupdict()
            if d['offset'] is not None:
                (lon1, lat1) = go2lonlat(loc_provider[d['loc']]['lon'], 
                                         loc_provider[d['loc']]['lat'], 
                                        d['drct'], float(d['offset']) )
            else:
                (lon1, lat1) = (loc_provider[d['loc']]['lon'], 
                                loc_provider[d['loc']]['lat'])
            lats.append( lat1 )
            lons.append( lon1 )
            #print '%s [%s,%s] -> %s,%s' % (l, loc_provider[d['loc']]['lon'],
            #                               loc_provider[d['loc']]['lat'],
            #                               lon1, lat1)
    if geotype == 'ISOL' or diameterstr is not None:
        lats2 = []
        lons2 = []
        diameter = float(diameterstr.replace("D", ""))
        # Approximation
        diameterdeg = diameter / 110.
        # UR
        lons2.append( lons[0] - diameterdeg )
        lats2.append( lats[0] + diameterdeg )
        # UL
        lons2.append( lons[0] + diameterdeg )
        lats2.append( lats[0] + diameterdeg )
        # LL
        lons2.append( lons[0] + diameterdeg )
        lats2.append( lats[0] - diameterdeg )
        # LR
        lons2.append( lons[0] - diameterdeg )
        lats2.append( lats[0] - diameterdeg )
        lons = lons2
        lats = lats2
        
    if geotype == 'LINE':
        lats2 = []
        lons2 = []
        # Figure out left hand points
        for i in range(0, len(lats)-1):
            deltax = lons[i+1] - lons[i]
            deltay = lats[i+1] - lats[i]
            if deltax == 0:
                deltax = 0.001
            angle = math.atan(deltay/deltax)
            runx = 0.1 * math.cos(angle)
            runy = 0.1 * math.sin(angle)
            # UR
            lons2.append( lons[i] - runy )
            lats2.append( lats[i] + runx )
            # UL
            lons2.append( lons[i+1] - runy )
            lats2.append( lats[i+1] + runx )
            
        for i in range(0, len(lats)-1):
            deltax = lons[i+1] - lons[i]
            deltay = lats[i+1] - lats[i]
            if deltax == 0:
                deltax = 0.001
            angle = math.atan(deltay/deltax)
            runx = 0.1 * math.cos(angle)
            runy = 0.1 * math.sin(angle)
            # LL
            lons2.append( lons[i+1] + runy )
            lats2.append( lats[i+1] - runx )
            # LR
            lons2.append( lons[i] + runy )
            lats2.append( lats[i] - runx )

        lons = lons2
        lats = lats2

    return lons, lats

def compute_esol(pts, distance):
    """ Figure out the box points given the two points and the distance """
    newpts = []
    deltax = pts[1][0] - pts[0][0]
    deltay = pts[1][1] - pts[0][1]
    # Compute unit vector
    linedistance = (deltax**2 + deltay**2)**0.5
    deltax = deltax / linedistance
    deltay = deltay / linedistance
    N = distance / 111.0 # approx
    newpts.append( [ pts[0][0] - N*deltay, pts[0][1] + N*deltax] )
    newpts.append( [ pts[1][0] - N*deltay, pts[1][1] + N*deltax] )
    newpts.append( [ pts[1][0] + N*deltay, pts[1][1] - N*deltax] )
    newpts.append( [ pts[0][0] + N*deltay, pts[0][1] - N*deltax] )
    newpts.append( [ newpts[0][0], newpts[0][1] ])

    return newpts

class SIGMETProduct( TextProduct ):
    '''
    Represents a Storm Prediction Center Mesoscale Convective Discussion
    '''
    
    def __init__(self, text, utcnow=None, ugc_provider=None, 
                 nwsli_provider=None):
        ''' constructor '''
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.sigmets = []
        if self.afos in ['SIGC','SIGW','SIGE']:
            self.process_SIGC()
        elif self.afos[:2] == 'WS':
            self.process_WS()
        else:
            self.process_ocean()
            
    def sql(self, txn):
        """ Do SQL related stuff that is required """
        txn.execute("DELETE from sigmets_current where expire < now()")
        for sigmet in self.sigmets:
            for table in ('sigmets_current', 'sigmets_archive'):
                sql = "DELETE from "+table+" where label = %s and expire = %s"
                args = (sigmet.label, sigmet.ets)
                txn.execute(sql, args)
                sqlwkt = "SRID=4326;%s" % (sigmet.geom.wkt,)
                sql = """INSERT into """+table+"""(sigmet_type, label, issue, 
                    expire, raw, geom) VALUES ('C',%s, %s, %s, %s,
                   %s)""" 
                args = (sigmet.label, self.valid, sigmet.ets, sigmet.raw, sqlwkt)
                txn.execute(sql, args)
            # Compute who is impacted by this SIGMET
            txn.execute("""
            SELECT distinct id from cwsu WHERE
            st_overlaps(geomFromEWKT('SRID=4326;%s'), geom) or 
            st_contains(geomFromEWKT('SRID=4326;%s'), geom) """ % (
                                                        sigmet.geom, 
                                                        sigmet.geom))
            for row in txn:
                sigmet.centers.append( row['id'] )
                
    def compute_time(self, ddhhmi):
        """ Convert this string into a proper date time """
        day = int(ddhhmi[:2])
        hour = int(ddhhmi[2:4])
        minute = int(ddhhmi[4:6])
        ts = self.valid
        if self.valid.day > 25 and day < 5: # next month
            ts += datetime.timedelta(days=15)
        
        return ts.replace(day=day, hour=hour, minute=minute)
        
    def process_ocean(self):
        """ Process oceananic """
        meat = self.unixtext.replace("\n", " ")
        m = O_LINE1.search(meat)
        d = m.groupdict()
        if d is None:
            raise SIGMETException("Failed to parse O_LINE1: %s" % (meat,))
        s = SIGMET()
        s.label = "%s %s" % (d['name'], d['num'])
        s.sts = self.compute_time(d['sts'])
        s.ets = self.compute_time(d['ets'])
        m = re.findall(O_PAIRS, meat)
        if len(m) == 0:
            # TODO: resolve what SIGMET cancels are
            if meat.find("CNL SIGMET") > 0:
                return
            raise SIGMETException("Failed to parse 0_PAIRS: %s" % (meat,))
        pts = []
        for pair in m:
            lat = float(pair[0][1:]) / 100.0
            if pair[0][0] == 'S':
                lat = 0 - lat
            lon = float(pair[1][1:]) / 100.0
            if pair[1][0] == 'W':
                lon = 0 - lon
            pts.append((lon,lat))
        m = LINE_RE.search(meat)
        if m is not None:
            d = m.groupdict()
            pts = compute_esol(pts, int(d['distance']))
        m = CIRCLE_RE.search(meat)
        if m is not None and len(pts) == 1:
            d = m.groupdict()
            # buffer a point, approximate 1 deg as 100 km :/
            s.geom = Point(pts[0]).buffer(float(d['distance'])*KM_SM / 100.)
        else:
            s.geom = Polygon(pts)
        
        s.raw = self.unixtext
        self.sigmets.append( s )

    def process_SIGC(self):
        """ Process this type of SIGMET """
        for section in self.unixtext.split('\n\n'):
            s = CS_RE.search(section.replace("\n", ' '))
            if s is None:
                continue
                #raise SIGMETException("Failed to parse CS_RE: %s" % (section,))
            data = s.groupdict()
            sig = SIGMET()
            sig.label = data['label']
            sig.areatext = data['states']
            sig.ets = figure_expire(self.valid, int(data['hour']), 
                               int(data['minute']))
            lons, lats = locs2lonslats(self.nwsli_provider,
                                       data['locs'], data['geotype'], 
                                       data['width'], data['diameter'])
            
            if len(lons) == 2:
                continue
            pts = []
            for lon,lat in zip(lons,lats):
                pts.append((lon, lat))
            if lats[0] != lats[-1] or lons[0] != lons[-1]:
                pts.append((lons[0], lats[0]))
            sig.geom = Polygon(pts)
            sig.raw = section
      
            self.sigmets.append(sig)
      
    def process_WS(self):
        """ Process this type of SIGMET """
        pass
    
    def get_jabbers(self, uri, uri2):
        """ Return the Jabber for this sigmet """
        j = []
        for sig in self.sigmets:
            area = " for "+ sig.areatext if sig.areatext != "" else ""
            txt = "%s issues SIGMET %s%s till %s UTC" % (self.source, sig.label,
                                                  area,
                                                  sig.ets.strftime("%H%M"))
            html = "<p>%s issues SIGMET %s%s till %s UTC</p>" % (self.source, 
                                                          sig.label,
                                                          area,
                                                sig.ets.strftime("%H%M"))
            channels = ["SIGMET.%s" % (i,) for i in sig.centers]
            channels.append("SIGMET.%s" % (self.source[1:],))
            xtra = {
                    'channels': ",".join(channels),
                    'twitter': txt
                    }
            
            j.append( [txt,html,xtra] )
        return j
    
    def draw(self):
        ''' For debugging, draw the polygons!'''
        from descartes.patch import PolygonPatch
        from pyiem.plot import MapPlot
        for sig in self.sigmets:
            m = MapPlot(sector='conus')
            x,y = m.map(sig.geom.exterior.xy[0], sig.geom.exterior.xy[1])
            patch = PolygonPatch(Polygon(zip(x,y)), fc='r', label='Outlook')
            m.ax.add_patch(patch)
            fn = '/tmp/%s.png' % (sig.label,)
            print ':: creating plot %s' % (fn,)
            m.postprocess(filename=fn )
            m.close()

def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function '''
    return SIGMETProduct( text, utcnow, ugc_provider, nwsli_provider )