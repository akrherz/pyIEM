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
    conus_sz = np.shape(CONUS)[0]
    cw_polygons = []
    ccw_polygons = []
    interior = None
    for i, segment in enumerate(segments):
        if segment[0] == segment[-1]:
            print '===== segment %s is interior polygon!' % (i,)
            interior = segment
            continue
        
        ls = LineString(segment)
        if ls.is_valid:
            newls = LineString(segment).intersection(CONUSPOLY)
            if newls.is_valid:
                x,y = newls.xy
                segment = zip(x,y)
        else:
            print '---------> INVALID LINESTRING? |%s|' % (str(segments),)
        distance = ((CONUS[:,0] - segment[0][0])**2 + 
                    (CONUS[:,1] - segment[0][1])**2)**.5
        idx1 = np.argmin(distance) 
        distance = ((CONUS[:,0] - segment[-1][0])**2 + 
                    (CONUS[:,1] - segment[-1][1])**2)**.5
        idx2 = np.argmin(distance)

        poly = np.array( segment )
        if idx2 > (conus_sz * 0.75) and idx1 < (conus_sz * .25):
            print 'i:%s idx1:%s idx2:%s Crossing start/finish line in CCW' % (i,
                                                    idx1, idx2)
            poly = np.concatenate([poly, CONUS[idx2:]])
            poly = np.concatenate([poly, CONUS[:idx1]])
            ccw_polygons.append( Polygon(np.vstack([poly, poly[0,:]])).buffer(0) )
        elif idx2 < (conus_sz * 0.25) and idx1 > (conus_sz * .75):
            print 'i:%s idx1:%s idx2:%s Crossing start/finish line in CW' % (i,
                                                    idx1, idx2)
            poly = np.concatenate([poly, CONUS[idx2:idx1]])
            cw_polygons.append( Polygon(np.vstack([poly, poly[0,:]])).buffer(0) )
        elif idx2 > idx1: # Simple case
            print 'i:%s idx1:%s idx2:%s Simple CW' % (i, idx1, idx2)
            poly = np.concatenate([poly, CONUS[idx2:]])
            poly = np.concatenate([poly, CONUS[:idx1]])
            cw_polygons.append( Polygon(np.vstack([poly, poly[0,:]])).buffer(0) )
        elif idx1 > idx2: # Simple case
            poly = np.concatenate([poly, CONUS[idx2:idx1]])
            newpolys = Polygon(np.vstack([poly, poly[0,:]])).buffer(0)
            if newpolys.geom_type == 'Polygon':
                newpolys = [newpolys]
            for poly in list(newpolys):
                print 'i:%s idx1:%s idx2:%s type: %s Simple CCW' % (i, idx1, idx2,
                                                                type(poly))
                ccw_polygons.append( poly )

    res = []    
    for i, ccwpoly in enumerate(ccw_polygons):
        if not ccwpoly.is_valid:
            print 'ERROR: ccwpoly %s is invalid!' % (i,)
            continue
        print '-> Running check for CCW polygon: %s area: %s type: %s' % (i,
                                                                 ccwpoly.area,
                                                            type(ccwpoly))
        for j, cwpoly in enumerate(cw_polygons):
            if not cwpoly.is_valid:
                print 'ERROR: cwpoly %s is invalid!' % (j,)
                continue
            print '--> checking against cwpoly %s' % (j,)
            if ccwpoly.overlaps(cwpoly):
                ccwpoly = ccwpoly.intersection(cwpoly)
                print '---> ccwpoly %s overlaps cwpoly %s result %s' % (i,j,
                                                        type(ccwpoly))
        res.append( ccwpoly )
    if len(ccw_polygons) == 0:
        respoly = cw_polygons[0]
        for i in range(1, len(cw_polygons)):
            print 'Running cw intersection for polygon %s' % (i,)
            respoly = respoly.intersection(cw_polygons[i])
        if interior:
            print 'Setting interior polygon to this polygon!'
            respoly = Polygon(list(respoly.exterior.coords), [interior])
        return MultiPolygon([ respoly ])
    
    return MultiPolygon(res)
    
    start_intersections = []
    end_intersections = []
    for segment in segments:
        distance = ((CONUS[:,0] - segment[0][0])**2 + 
                    (CONUS[:,1] - segment[0][1])**2)**.5
        distance2 = ((CONUS[:,0] - segment[1][0])**2 + 
                    (CONUS[:,1] - segment[1][1])**2)**.5
        if np.min(distance2) < np.min(distance) and len(segment) > 3:
            segment.pop(0)
            distance = distance2
        start_intersections.append( np.argmin(distance) )
        distance = ((CONUS[:,0] - segment[-1][0])**2 + 
                    (CONUS[:,1] - segment[-1][1])**2)**.5
        distance2 = ((CONUS[:,0] - segment[-2][0])**2 + 
                    (CONUS[:,1] - segment[-2][1])**2)**.5
        if np.min(distance2) < np.min(distance) and len(segment) > 3:
            segment.pop(0)
            distance = distance2
        end_intersections.append( np.argmin(distance) )
        
    ''' First, we need to figure out which points along the edge of the
    CONUS domain do we actually care about '''
    conus_sz = np.shape(CONUS)[0]
    usepts = np.ones( np.shape(CONUS)[0] )
    (cw, ccw) = range(2)
    directions = []
    for i, (idx1, idx2) in enumerate(zip(start_intersections, end_intersections)):
        if idx2 > (conus_sz * 0.75) and idx1 < (conus_sz * .25):
            print 'i:%s idx1:%s idx2:%s Crossing start/finish line in CCW' % (i,
                                                    idx1, idx2)
            usepts[idx1:idx2+1] = 0.
            directions.append( ccw )            
        elif idx2 < (conus_sz * 0.25) and idx1 > (conus_sz * .75):
            print 'i:%s idx1:%s idx2:%s Crossing start/finish line in CW' % (i,
                                                    idx1, idx2)
            usepts[0:idx2] = 0.
            usepts[idx1:] = 0.
            directions.append( cw )            
        elif idx2 > idx1: # Simple case
            print 'i:%s idx1:%s idx2:%s Simple CW' % (i, idx1, idx2)
            usepts[idx1:idx2] = 0.
            directions.append( cw )            
        elif idx1 > idx2: # Simple case
            print 'i:%s idx1:%s idx2:%s Simple CCW' % (i, idx1, idx2)
            usepts[0:idx2] = 0.
            usepts[idx1:] = 0.
            directions.append( ccw )            

    ''' Now comes the tricky parts '''
    print 'usepts counts: 0: %s 1: %s ' % (np.sum(np.where(usepts==0,1,0)),
                                           np.sum(usepts))
    res = []
    if cw not in directions:
        print 'All CCW segments found!'
        for i in range(len(segments)):
            idx1 = end_intersections[i]
            idx2 = start_intersections[i]
            poly = CONUS[idx1:idx2]
            poly = np.concatenate([poly, segments[i]])
            res.append( Polygon(np.vstack([poly, poly[0,:]])) )
        return MultiPolygon(res)
    
    if np.max(usepts) == 0:
        print '... Entire CONUS negated, attempting different logic'
        for i, thisdir in enumerate(directions):
            if thisdir == cw:
                continue
            startidx = start_intersections[i]
            endidx = end_intersections[i]
            print '... found CCW segment %s with startidx: %s endidx: %s' % (
                                        i, startidx, endidx)
            
    
    idx = list(usepts).index(1)
    poly = None
    usedsegs = []
    print '---------------------------------------------------'
    while idx < conus_sz:
        print '--> Staring this loop with idx of %s/%s' % (idx, conus_sz)
        travel = list(usepts[idx:]).index(0)
        idx2 = idx+travel
        ''' Figure out which segement starts at this '''
        print 'Looking for %s in %s' % (idx2, ','.join(map(str,start_intersections)))
        segid = start_intersections.index(idx2)
        print 'Loop iteration idx: %s idx2: %s segid: %s' % (idx, idx2, segid)
        if segid in usedsegs:
            res.append( Polygon(np.vstack([poly, poly[0,:]])) )
            poly = None
        else:
            usedsegs.append(segid)
            if poly is None:
                poly = CONUS[idx:idx2]
            else:
                poly = np.concatenate([poly, CONUS[idx:idx2]])
            poly = np.concatenate([poly, segments[segid]])
        print 'usepts status idx2: %s min: %s max: %s' % (idx2,
                                                 np.min(usepts[idx2:]),
                                                 np.max(usepts[idx2:]))
        if np.max(usepts[idx2:]) == 0:
            print 'End of circle'
            res.append( Polygon(np.vstack([poly, poly[0,:]])) )
            idx = conus_sz
        else:
            idx = idx2 + list(usepts[idx2:]).index(1)
            if np.min(usepts[idx:]) == 1:
                print 'Ride circle to the end!'
                poly = np.concatenate([poly, CONUS[idx:]])
                res.append( Polygon(np.vstack([poly, poly[0,:]])) )
                idx = conus_sz
       
                   
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
                        print 'Category:', category, 'Threshold:', threshold
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
                