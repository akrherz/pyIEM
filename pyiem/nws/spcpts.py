"""
 Something to deal with SPC PTS Product
 My life was not supposed to end like this, what a brutal format
"""
import re
import numpy as np

from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely.geometry.polygon import LinearRing
import datetime
import copy
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

def get_segments_from_text(text):
    """ Return list of segments for this text """
    tokens = re.findall("([0-9]{8})", text.replace("\n",""))
    # First we generate a list of segments, based on what we found 
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
    if len(pts) > 0:
        segments.append( pts )

    return segments

def str2multipolygon(s):
    """ Convert string PTS data into a polygon
    """
    segments = get_segments_from_text(s)
    
    # Simple case whereby the segment is its own circle, thank goodness
    if (len(segments) == 1 and 
        segments[0][0][0] == segments[0][-1][0] and
        segments[0][0][1] == segments[0][-1][1]):
        print 'Single closed polygon found, done and done'
        return MultiPolygon([Polygon( segments[0] )])
    
    # We have some work to do
    load_conus_data()

    # We start with just a conus polygon and we go from here, down the rabbit
    # hole
    polys = [copy.deepcopy(CONUSPOLY),]

    for i, segment in enumerate(segments):
        print 'Iterate: %s/%s, len(segment): %s (%.1f %.1f) (%.1f %.1f)' % (
                i+1, len(segments), len(segment), segment[0][0], segment[0][1], 
                                segment[-1][0],
                                        segment[-1][1])
        if segment[0] == segment[-1]:
            print '     segment %s is closed polygon!' % (i,)
            lr = LinearRing( LineString(segment))
            if not lr.is_ccw:
                print '     polygon is counter-clockwise (exterior)'
                polys.insert(0, Polygon(segment) )
                continue
            print '     polygon is clockwise (interior), compute to which poly'
            found = False
            for j, poly in enumerate(polys):
                if poly.intersection(lr):
                    interiors = [l for l in polys[j]._interiors]
                    interiors.append( lr )
                    newp = Polygon(polys[j].exterior, interiors)
                    if newp.is_valid:
                        polys[j] = newp
                        print ('     polygon is interior to polys #%s, '
                           +'area now %.2f') % (j, polys[j].area)
                    else:
                        raise Exception(('Adding interior polygon resulted '
                                        +'in an invalid geometry, aborting'))
                    found = True
                    break
            if not found:
                print '      ERROR: did not find intersection!'
            continue
    
        # Attempt to 'clean' this string against the CONUS Polygon
        ls = LineString(segment)
        if ls.is_valid:
            newls = ls.intersection(CONUSPOLY)
            if newls.is_valid:
                if newls.geom_type == 'MultiLineString':
                    print '     intersection with conuspoly found %s segments' % (
                                                len(newls.geoms),)
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

        # Figure out which polygon this line intersects
        found = False
        for j, poly in enumerate(polys):
            if not poly.intersection(ls):
                continue
            found = True
            # Compute the intersection points of this segment and what 
            # is left of the pie                    
            x,y = poly.exterior.xy
            pie = np.array( zip(x,y) )
            distance = ((pie[:,0] - line[0,0])**2 + 
                        (pie[:,1] - line[0,1])**2)**.5
            idx1 = np.argmin(distance) -1
            distance = ((pie[:,0] - line[-1,0])**2 + 
                        (pie[:,1] - line[-1,1])**2)**.5
            idx2 = np.argmin(distance) +1

            sz = np.shape(pie)[0]
            print '     computed intersections idx1: %s/%s idx2: %s/%s' % (idx1,
                                                            sz, idx2, sz)
            if idx1 < idx2:
                print '     CASE 1: idx1:%s idx2:%s Crosses start finish' % (
                    idx1, idx2)
                # We we piece the puzzle together!
                line = np.concatenate([line, pie[idx2:]])
                line = np.concatenate([line, pie[:idx1]])
                pie = line
                polys[j] = Polygon(pie, polys[j].interiors)
                print '     replacing polygon index: %s area: %.2f' % (j, 
                                                            polys[j].area)
            elif idx1 > idx2:
                print '     CASE 2 idx1:%s idx2:%s' % (idx1, idx2)
                line = np.concatenate([line, pie[idx2:idx1]])
                polys.append( Polygon(line))
                print '     + adding polygon'
            else:
                raise Exception('this should not happen, idx1 == idx2!')

            break
        
        if not found:
            print '     segment did not intersect' 

    res = []    
    print 'Resulted in len(polys): %s, now quality controlling' % (len(polys),)
    for i, p in enumerate(polys):
        if not p.is_valid:
            print '     ERROR: polygon %s is invalid!' % (i,)
            continue
        if p.area == CONUSPOLY.area:
            print '     polygon %s is just CONUS, skipping' % (i,)
            continue
        print '     polygon: %s has area: %s' % (i, p.area)
        res.append( p )
    if len(res) == 0:
        raise Exception("Processed no geometries, this is a bug!")
    return MultiPolygon(res)

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
    
    def get_outlook(self, category, threshold):
        ''' Get an outlook by category and threshold '''
        for outlook in self.outlooks:
            if outlook.category == category and outlook.threshold == threshold:
                return outlook
        return None
    
    def draw_outlooks(self):
        ''' For debugging, draw the outlooks on a simple map for inspection!'''
        from descartes.patch import PolygonPatch
        import matplotlib.pyplot as plt
        load_conus_data()
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
            fn = '/tmp/%s_%s_%s.png' % (self.issue.strftime("%Y%m%d%H%M"),
                                        outlook.category, outlook.threshold)
            print ':: creating plot %s' % (fn,)
            fig.savefig( fn )
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
        for segment in tp.text.split("&&")[:-1]:
            # We need to figure out the probabilistic or category
            tokens = re.findall("\.\.\. (.*) \.\.\.", segment)
            category = tokens[0].strip()
            point_data = {}
            # Now we loop over the lines looking for data
            threshold = None
            for line in segment.split("\n"):
                if re.match("^(D[3-8]\-?[3-8]?|EXTM|MRGL|ENH|SLGT|MDT|HIGH|CRIT|TSTM|SIGN|0\.[0-9][0-9]) ", line) is not None:
                    newthreshold = line.split()[0]
                    if threshold is not None and threshold == newthreshold:
                        point_data[threshold] += " 99999999 "
                    threshold = newthreshold
                if threshold is None:
                    continue
                if not point_data.has_key(threshold):
                    point_data[threshold] = ""
                point_data[threshold] += line.replace(threshold, " ")
                
            for threshold in point_data.keys():
                print "==== Category: '%s' Threshold; '%s' =====" % (category, 
                                                                    threshold)
                mp = str2multipolygon( point_data[threshold]  )
                self.outlooks.append( SPCOutlook(category, threshold, mp) ) 
                