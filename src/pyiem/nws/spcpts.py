# Something to deal with SPC PTS Product
import re
import shapelib
from ctypes import c_void_p, byref
import numpy

from shapely.geometry import Polygon, LineString, Point
from shapely.geometry.base import geom_factory
import shapely.geos
import datetime

def ptchecker(pts):
    """
    Do some work on the line, buffer if necessary
    """
    data = numpy.array( pts )
    if data[0,0] == data[-1,0] and data[0,1] == data[-1,1]:
        print 'I found a closed line segment, returning'
        return data
    # We wish to extend the lines slightly to make sure they intersect
    # We'll go 0.2 deg, make sure non zero
    dx = data[1,0] - data[0,0] + 0.00001
    dy = data[1,1] - data[0,1] + 0.00001
    if abs(dx) > abs(dy):
        x = data[0,0] - 1. * (abs(dx)/dx)
        y = data[0,1] - 1. * (abs(dy)/abs(dx)) * (abs(dy)/dy)
    elif abs(dy) > abs(dx):
        y = data[0,1] - 1. * (abs(dy)/dy)
        x = data[0,0] - 1. * (abs(dx)/abs(dy)) * (abs(dx)/dx)
    else:
        y = data[0,1] - 1. * (abs(dy)/dy)
        x = data[0,0] - 1. * (abs(dx)/dx)
    print 'Extender Start: New: %.2f %.2f P0: %s P1: %s' % (x,y, 
                                                data[0,:], data[1,:])
    pts.insert(0, [x,y] )
    # Now we do the last point, extend it some
    dx = data[-1,0] - data[-2,0] + 0.00001
    dy = data[-1,1] - data[-2,1] + 0.00001
    if abs(dx) > abs(dy):
        x = data[-1,0] + 1. * (abs(dx)/dx)
        y = data[-1,1] + 1. * (abs(dy)/abs(dx)) * (abs(dy)/dy)
    elif abs(dy) > abs(dx):
        y = data[-1,1] + 1. * (abs(dy)/dy)
        x = data[-1,0] + 1. * (abs(dx)/abs(dy)) * (abs(dx)/dx)
    else:
        y = data[-1,1] + 1. * (abs(dy)/dy)
        x = data[-1,0] + 1. * (abs(dx)/dx)
    print 'Extender End: P-2: %s P-1: %s New: %.2f %.2f' % (
                                                data[-2,:], data[-1,:], x, y)
    pts.append( [x,y] )
    
    return numpy.array( pts )
    
def rightpoint(segment):
    
    mid = int(numpy.shape(segment)[0] / 2. )
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
    
    
        
def str2pts(s):
    """
    Convert string PTS data into an array of line segments
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
            segments.append( ptchecker(pts) )
            pts = []
        else:
            pts.append( [lon, lat] )
    segments.append( ptchecker(pts) )
    return segments

def read_poly():
    _shp = shapelib.open('/home/ldm/pyWWA/tables/conus.shp')
    _poly = _shp.read_object(0)
    _data = numpy.array( _poly.vertices()[0] )
    return Polygon( _data )

CONUSPOLY = read_poly()

class SPCOutlook(object):

    def __init__(self, category, threshold, polygon, line):
        self.category = category
        self.threshold = threshold
        self.polygon = polygon
        self.line = numpy.array(line)

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
        import matplotlib.pyplot as plt
        i = 0
        for outlook in self.outlooks:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            x, y = CONUSPOLY.exterior.xy
            ax.plot(x,y, color='b', label='Conus')
            x,y = outlook.polygon.exterior.xy
            ax.plot(x, y, color='r', label='Outlook')
            x = outlook.line[:,0]
            y = outlook.line[:,1]
            ax.plot(x, y, color='g', label='SPC Orig')
            ax.text(x[0], y[0], 'Start')
            ax.text(x[-1], y[-1], 'End')
            ax.set_title('Category %s Threshold %s' % (outlook.category, 
                                                   outlook.threshold))
            ax.legend(loc=3)
            fig.savefig('%02d.png' % (i,))
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
        # First we split the product by &&
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
                        self.consumer(category, threshold, data)
                    threshold = line.split()[0]
                    data = ""
                if threshold is None:
                    continue
                data += line
                
            if threshold is not None:
                self.consumer(category, threshold, data)
                
    def consumer(self, category, threshold, data):
        """
        Actually do stuff
        """
        hasmore = False
        # Compute our array of given points, each time we hit 99999999 this is a
        # break, so we'll make the array multidimensional
        segments = str2pts( data  )
        print '%s %s Found %s line segment(s)' % (category, threshold, 
                                                len(segments))
        mypoly = CONUSPOLY
        geomc = None
        polygons = None
        collection = None
        rpt = None
        geom_array = None
        # Now we loop over the segments
        for segment in segments:
            # Check to see if we have a polygon, if so, our work is done!
            if segment[0,0] == segment[-1,0] and segment[0,1] == segment[-1,1]:
                self.outlooks.append( SPCOutlook(category, threshold,
                                                 Polygon( segment ), segment ) ) 
                continue

            # Darn, we have some work to do
            line = LineString( segment )
            # Union this line with the conus polygon
            geomc = mypoly.boundary.union( line )
            geom_array_type = c_void_p * 1
            geom_array = geom_array_type()
            geom_array[0] = geomc._geom
            polygons = shapely.geos.lgeos.GEOSPolygonize(byref(geom_array),1)
            collection = geom_factory(polygons)
            rpt = rightpoint( segment )
            print 'Looking for %s' % (rpt,)
            for i in range(len(collection)):
                print "Polyon %s %s has centroid %s" % (i, collection[i].area,
                                                        collection[i].centroid)
                if collection[i].contains(rpt):
                    print 'Found Polygon %s' % (i,)
                    x,y = collection[i].exterior.xy
                    mypoly = Polygon( zip(x,y) )
                    print 'Found Polygon %s Area: %.4f Len collection %s' % (
                                                i, mypoly.area, len(collection))
            hasmore = True
    
        if hasmore:
            x,y = mypoly.exterior.xy
            ar = zip(x,y)
            self.outlooks.append( SPCOutlook(category, threshold, 
                                             Polygon( ar ), segment ) )
        del mypoly
        del geomc
        del polygons
        del geom_array
        del collection
        del rpt