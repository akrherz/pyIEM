"""
 Something to deal with SPC PTS Product
 My life was not supposed to end like this, what a brutal format
"""
import re
import shapelib
from ctypes import c_void_p, byref
import numpy as np

from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.geometry.base import geom_factory
from shapely.geometry.polygon import LinearRing, orient
import shapely.geos
import datetime
import os

CONUS = None
CONUSPOLY = None

def load_conus_data():
    """ Load up the conus datafile for our perusal """
    global CONUS, CONUSPOLY
    if CONUS is not None:
        return
    fn = "%s/../data/conus_marine_bnds.txt" % (os.path.dirname(__file__),)
    lons = []
    lats = []
    for line in open(fn):
        tokens = line.split(",")
        lons.append( float(tokens[0]) )
        lats.append( float(tokens[1]) )
    CONUS = np.column_stack([lons,lats])
    CONUSPOLY = Polygon( CONUS ) 
    
def ptchecker(pts):
    """
    Do some work on the line, buffer if necessary
    """
    data = np.array( pts )
    if data[0,0] == data[-1,0] and data[0,1] == data[-1,1]:
        print 'I found a closed line segment, returning'
        return data
    load_conus_data()
    distance = ((CONUS[:,0] - data[0,0])**2 + (CONUS[:,1] - data[0,1])**2)**.5
    idx2 = np.argmin(distance)
    distance = ((CONUS[:,0] - data[-1,0])**2 + (CONUS[:,1] - data[-1,1])**2)**.5
    idx1 = np.argmin(distance)
    # The -1 data index would be the start of the CW conus
    if idx1 < idx2: # Simple
        data = np.concatenate([data, CONUS[idx1:idx2+1,:]])
    if idx1 > idx2: # we cross the start-finish line of our CONUS bounds
        data = np.concatenate([data, CONUS[idx1:-1,:]])
        data = np.concatenate([data, CONUS[:idx2+1,:]])
    # Now we make our endpoints match for a closed circle
    data = np.concatenate([data, data[-1,:]])
    
    return data
    
def rightpoint(segment):
    
    mid = int(np.shape(segment)[0] / 2. )
    x1, y1 = segment[mid,:]
    x0, y0 = segment[mid-1,:]
    dx = x1 - x0
    dy = y1 - y0
    # Going north
    if dx == 0 and dy > 0:
        right = [x0 + 0.1, y0 + dy*0.5]
    # Going east
    elif dy == 0 and dx > 0:
        right = [x0 + dx*0.5, y0 - 0.2]
    # Going south
    elif dx == 0 and dy < 0:
        right = [x0 - 0.1, y0 + dy*.5]
    # Going west
    elif dx < 0 and dy == 0:
        right = [x0 + dx*.5, y0 + 0.2]
    # Going NE
    elif dx > 0 and dy > 0:
        right = [x0 + dx*0.5, y0 ]
    # Going SE
    elif dx > 0 and dy < 0:
        right = [x0 , y0 + dy*0.5]
    # Going SW
    elif dx < 0 and dy < 0:
        right = [x0 + dx*.5, y0 ]
    # Going NW
    else:
        right = [x0 , y0 + dy*0.5]

    
    #fp = "%s.png" % (segment[0,1],)
    #fig = plt.figure()
    #ax = fig.add_subplot(111)
    #ax.plot( segment[:,0], segment[:,1], color='r' )
    #x,y = CONUSPOLY.exterior.xy
    #ax.plot(x, y, color='b')
    #ax.scatter( right[0], right[1] )
    
    #ax.plot( segment[0,0], segment[0,1], marker="+", color='#000000')
    #fig.savefig(fp)
        
    return Point( right )
    
    
        
def str2multipolygon(s):
    """
    Convert string PTS data into a polygon
    """
    tokens = re.findall("([0-9]{8})", s.replace("\n",""))
    ''' First we generate a list of segments, based on what we found '''
    segments = []
    pts = []
    for token in tokens:
        lat = float(token[:4]) / 100.0
        lon = 0 - (float(token[-4:]) / 100.0)
        if lon > -30:
            lon -= 100.
        if token == '99999999':        
            segments.append( pts )
            pts = []
        else:
            pts.append( [lon, lat] )
    segments.append( pts )
    
    ''' Simple case whereby the segment is its own circle, thank goodness '''
    if (len(segments) == 1 and segments[0][0][0] == segments[0][-1][0] and
        segments[0][0][1] == segments[0][-1][1]):
        print 'We have a lone circle, horray'
        return MultiPolygon([Polygon( segments[0] )])
    
    ''' We have some work to do '''
    load_conus_data()
    pie = CONUS

    current_exterior = None
    current_interior = []
    polys = []
    
    for i, segment in enumerate(segments):
        print 'Iterate: %s/%s, len(segment): %s' % (i+1, len(segments), 
                                                    len(segment))
        if segment[0] == segment[-1]:
            print '     segment %s is closed polygon!' % (i,)
            lr = LinearRing( LineString(segment))
            if not lr.is_ccw:
                print '     segment %s is clockwise!' % (i,)
                if current_exterior is not None:
                    print '     Creating Polygon as we have two CW polys!'
                    polys.append( Polygon(current_exterior, current_interior))
                current_exterior = segment
                continue
            if current_exterior is None:
                raise Exception("Found interior with no exterior! aborting...")
            current_interior.append( Polygon(segment) )
            continue
        
        if current_exterior is not None:
            print '     Creating Polygon because current_exterior is defined'
            polys.append( Polygon(current_exterior, current_interior))
            current_exterior = None
        
        ls = LineString(segment)
        if ls.is_valid:
            newls = ls.intersection(CONUSPOLY)
            if newls.is_valid:
                if newls.geom_type == 'MultiLineString':
                    maxlength = 0
                    for geom in newls.geoms:
                        if geom.length > maxlength:
                            newls2 = geom
                            maxlength = geom.length
                    newls = newls2
                x,y = newls.xy
                segment = zip(x,y)
            else:
                print '     Intersection landed here? %s' % (newls.is_valid,)
        else:
            print '---------> INVALID LINESTRING? |%s|' % (str(segments),)

        line = np.array( segment )

        ''' Compute the intersection points of this segment and what is left
            of the pie'''                    
        distance = ((pie[:,0] - line[0,0])**2 + 
                    (pie[:,1] - line[0,1])**2)**.5
        idx1 = np.argmin(distance) -1
        distance = ((pie[:,0] - line[-1,0])**2 + 
                    (pie[:,1] - line[-1,1])**2)**.5
        idx2 = np.argmin(distance) +1

        sz = np.shape(pie)[0]
        print '     computed intersections idx1: %s/%s idx2: %s/%s' % (idx1,
                                                                sz, idx2, sz)

        if idx2 > (sz * 0.75) and idx1 < (sz * .25):
            print '     CASE 1: idx1:%s idx2:%s Crossing start/finish line' % (
                idx1, idx2)
            ''' We we piece the puzzle together! '''
            line = np.concatenate([line, pie[idx2:]])
            line = np.concatenate([line, pie[:idx1]])
            pie = line

        elif idx2 < (sz * 0.25) and idx1 > (sz * .75):
            print '     CASE 2 idx1:%s idx2:%s outside of start finish' % (
                idx1, idx2)
            ''' We we piece the puzzle together! '''
            line = np.concatenate([pie[idx2:idx1], line])
            pie = line
        elif idx1 > idx2: # Simple case
            print '     CASE 3 idx1:%s idx2:%s Simple CCW' % (idx1, idx2)
            line = np.concatenate([line, pie[idx2:idx1]])
            pie = line
        elif idx2 > idx1: # Simple case
            print '     CASE 4 idx1:%s idx2:%s Simple CW' % (idx1, idx2)
            line = np.concatenate([pie[:idx1], line])
            line = np.concatenate([line, pie[idx2:]])
            pie = line
        else:
            raise Exception('this should not happen!')

    print '     Creating Polygon from what is left of pie, len(pie) = %s!' % (
                                                    np.shape(pie)[0],)
    polys.append( Polygon(pie) )


    res = []    
    print 'Resulted in len(polys): %s, now quality controlling' % (len(polys),)
    for i, p in enumerate(polys):
        if not p.is_valid:
            print '     ERROR: polygon %s is invalid!' % (i,)
            continue
        print '     polygon: %s has area: %s' % (i, p.area)
        res.append( p )
    if len(res) == 0:
        raise Exception("Processed no geometries, this is a bug!")
    return MultiPolygon(res)
    

def read_poly():
    _shp = shapelib.open('/home/ldm/pyWWA/tables/conus.shp')
    _poly = _shp.read_object(0)
    _data = np.array( _poly.vertices()[0] )
    return Polygon( _data )

#CONUSPOLY = read_poly()

class SPCOutlook(object):

    def __init__(self, category, threshold, multipoly):
        self.category = category
        self.threshold = threshold
        self.geometry = multipoly

class SPCPTS(object):

    def __init__(self, tp):
        self.outlooks = []
        self.valid = None
        self.expire = None
        self.issue = tp.valid
        self.set_metadata( tp )
        self.find_issue_expire( tp )
        self.find_outlooks( tp )
    
    def draw_outlooks(self):
        from descartes.patch import PolygonPatch
        import matplotlib.pyplot as plt
        load_conus_data()
        i = 0
        for outlook in self.outlooks:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.plot(CONUS[:,0],CONUS[:,1], color='b', label='Conus')
            for poly in outlook.geometry:
                patch = PolygonPatch(poly, fc='r', label='Outlook')
                ax.add_patch(patch)
            ax.set_title('Category %s Threshold %s' % (outlook.category, 
                                                   outlook.threshold))
            ax.legend(loc=3)
            fig.savefig('/tmp/%02d.png' % (i,))
            i+= 1
            del fig
            del ax
    
    def set_metadata(self, tp):
        """
        Set some metadata about this product
        """
        if tp.afos == 'PTSDY1':
            self.day  = '1'
            self.outlook_type = 'C'
        if tp.afos == "PTSDY2":
            self.day = '2'
            self.outlook_type = 'C'
        if tp.afos == "PTSDY3":
            self.day = '3'
            self.outlook_type = 'C'
        if tp.afos == "PTSD48":
            self.day = '4'
            self.outlook_type = 'C'
        if tp.afos == "PFWFD1":
            self.day = '1'
            self.outlook_type = 'F'
        if tp.afos == "PFWFD2":
            self.day = '2'
            self.outlook_type = 'F'
        if tp.afos == "PFWF38":
            self.day = '3'
            self.outlook_type = 'F'
    
    def find_issue_expire(self, tp ):
        """
        Determine the period this product is valid for
        """
        tokens = re.findall("VALID TIME ([0-9]{6})Z - ([0-9]{6})Z", tp.text)
        day1 = int(tokens[0][0][:2])
        hour1 = int(tokens[0][0][2:4])
        min1 = int(tokens[0][0][4:])
        day2 = int(tokens[0][1][:2])
        hour2 = int(tokens[0][1][2:4])
        min2 = int(tokens[0][1][4:])
        valid = tp.valid.replace(day=day1,hour=hour1,minute=min1)
        expire = tp.valid.replace(day=day2,hour=hour2,minute=min2)
        if day1 < tp.valid.day and day1 == 1:
            valid = tp.valid + datetime.timedelta(days=25)
            valid = valid.replace(day=day1,hour=hour1,minute=min1)
        if day2 < tp.valid.day and day2 == 1:
            expire = tp.valid + datetime.timedelta(days=25)
            expire = expire.replace(day=day2,hour=hour1,minute=min1)
        self.valid = valid
        self.expire = expire
    
    def find_outlooks(self, tp):
        """ Find the outlook sections within the text product! """
        data = ""
        for segment in tp.text.split("&&")[:-1]:
            # We need to figure out the probabilistic or category
            tokens = re.findall("\.\.\. (.*) \.\.\.", segment)
            category = tokens[0].strip()
            # Now we loop over the lines looking for data
            threshold = None
            for line in segment.split("\n"):
                if re.match("^(D[3-8]|EXTM|SLGT|MDT|HIGH|CRIT|TSTM|SIGN|0\.[0-9][0-9]) ", line) is not None:
                    if threshold is not None:
                        print '\n===== Category: %s Threshold: %s ======' % (
                                    category, threshold)
                        self.outlooks.append(SPCOutlook(category, threshold,
                                                 str2multipolygon( data  ) ) ) 
                    threshold = line.split()[0]
                    data = ""
                if threshold is None:
                    continue
                data += line
                
            if threshold is not None:
                print 'Category:', category, 'Threshold:', threshold
                self.outlooks.append(SPCOutlook(category, threshold,
                                                str2multipolygon( data  ) ) ) 
                