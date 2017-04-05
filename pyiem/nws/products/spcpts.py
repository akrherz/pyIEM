"""
 Something to deal with SPC PTS Product
 My life was not supposed to end like this, what a brutal format
"""
import re
import numpy as np
from pyiem.nws.product import TextProduct
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
    fn = "%s/../../data/conus_marine_bnds.txt" % (os.path.dirname(__file__),)
    lons = []
    lats = []
    for line in open(fn):
        tokens = line.split(",")
        lons.append(float(tokens[0]))
        lats.append(float(tokens[1]))
    CONUS = np.column_stack([lons, lats])
    CONUSPOLY = Polygon(CONUS)


def get_segments_from_text(text):
    """ Return list of segments for this text """
    tokens = re.findall("([0-9]{8})", text.replace("\n", ""))
    # First we generate a list of segments, based on what we found
    segments = []
    pts = []
    for token in tokens:
        lat = float(token[:4]) / 100.0
        lon = 0 - (float(token[-4:]) / 100.0)
        if lon > -30:
            lon -= 100.
        if token == '99999999':
            segments.append(pts)
            pts = []
        else:
            pts.append([lon, lat])
    if len(pts) > 0:
        segments.append(pts)

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
        return MultiPolygon([Polygon(segments[0])])

    # We have some work to do
    load_conus_data()

    # We start with just a conus polygon and we go from here, down the rabbit
    # hole
    polys = [copy.deepcopy(CONUSPOLY), ]

    for i, segment in enumerate(segments):
        print(('  Iterate: %s/%s, len(segment): %s (%.1f %.1f) (%.1f %.1f)'
               ) % (i+1, len(segments), len(segment), segment[0][0],
                    segment[0][1], segment[-1][0], segment[-1][1]))
        if segment[0] == segment[-1] and len(segment) > 2:
            print '     segment %s is closed polygon!' % (i,)
            lr = LinearRing(LineString(segment))
            if not lr.is_ccw:
                print '     polygon is counter-clockwise (exterior)'
                polys.insert(0, Polygon(segment))
                continue
            print '     polygon is clockwise (interior), compute to which poly'
            found = False
            for j, poly in enumerate(polys):
                if poly.intersection(lr):
                    interiors = [l for l in polys[j]._interiors]
                    interiors.append(lr)
                    newp = Polygon(polys[j].exterior, interiors)
                    if newp.is_valid:
                        polys[j] = newp
                        print ('     polygon is interior to polys #%s, '
                               'area now %.2f') % (j, polys[j].area)
                    else:
                        raise Exception(('Adding interior polygon resulted '
                                         'in an invalid geometry, aborting'))
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
                if newls.geom_type in ['MultiLineString',
                                       'GeometryCollection']:
                    print(('     intersection with conuspoly found %s segments'
                           ) % (len(newls.geoms),))
                    maxlength = 0
                    for geom in newls.geoms:
                        if geom.length > maxlength:
                            newls2 = geom
                            maxlength = geom.length
                    newls = newls2
                (x, y) = newls.xy
                segment = zip(x, y)
            else:
                print '     Intersection landed here? %s' % (newls.is_valid,)
        else:
            print '---------> INVALID LINESTRING? |%s|' % (str(segments),)

        line = np.array(segment)

        # Figure out which polygon this line intersects
        found = False
        for j in range(-1, -1 - len(polys), -1):
            if found:
                break
            poly = polys[j]
            print("     polys iter j=%s len(polys) = %s" % (j, len(polys)))
            if not poly.intersection(ls):
                print("    - linestring does not intersect poly, continue")
                continue
            found = True
            for q in range(5):
                # Compute the intersection points of this segment and what
                # is left of the pie
                (x, y) = poly.exterior.xy
                pie = np.array(zip(x, y))
                distance = ((pie[:, 0] - line[q, 0])**2 +
                            (pie[:, 1] - line[q, 1])**2)**.5
                idx1 = np.argmin(distance) - 1
                idx1 = idx1 if idx1 > -1 else 0
                distance = ((pie[:, 0] - line[0 - (q+1), 0])**2 +
                            (pie[:, 1] - line[0 - (q+1), 1])**2)**.5
                idx2 = np.argmin(distance) + 1
                idx2 = idx2 if idx2 > -1 else 0

                sz = np.shape(pie)[0]
                print(('     Q:%s computed intersections '
                       'idx1: %s/%s idx2: %s/%s'
                       ) % (q, idx1, sz, idx2, sz))
                if idx1 < idx2:
                    print(('     CASE 1: idx1:%s idx2:%s Crosses start finish'
                           ) % (idx1, idx2))
                    # We we piece the puzzle together!
                    tmpline = np.concatenate([line, pie[idx2:]])
                    tmpline = np.concatenate([tmpline, pie[:idx1]])
                    if Polygon(tmpline, polys[j].interiors).is_valid:
                        pie = tmpline
                        polys[j] = Polygon(pie, polys[j].interiors)
                        print(('     replacing polygon index: %s area: %.2f'
                               ) % (j, polys[j].area))
                    else:
                        continue
                elif idx1 > idx2:
                    print '     CASE 2 idx1:%s idx2:%s' % (idx1, idx2)
                    tmpline = np.concatenate([line, pie[idx2:idx1]])
                    polys.append(Polygon(tmpline))
                    print(('     + adding polygon index: %s area: %.2f'
                           ) % (len(polys) - 1, polys[-1].area))
                else:
                    raise Exception('this should not happen, idx1 == idx2!')
                print("     breaking out of q loop")
                break

        if not found:
            print '     segment did not intersect'

    res = []
    print(('  Resulted in len(polys): %s, now quality controlling'
           ) % (len(polys),))
    for i, p in enumerate(polys):
        if not p.is_valid:
            print '     ERROR: polygon %s is invalid!' % (i,)
            continue
        if p.area == CONUSPOLY.area:
            print '     polygon %s is just CONUS, skipping' % (i,)
            continue
        print '     polygon: %s has area: %s' % (i, p.area)
        res.append(p)
    if len(res) == 0:
        raise Exception(("Processed no geometries, this is a bug!\n"
                         "  s is %s\n"
                         "  segments is %s" % (repr(s), repr(segments))))
    return MultiPolygon(res)


class SPCOutlook(object):

    def __init__(self, category, threshold, multipoly):
        self.category = category
        self.threshold = threshold
        self.geometry = multipoly
        self.wfos = []


class SPCPTS(TextProduct):

    def __init__(self, text, utcnow=None, ugc_provider=dict(),
                 nwsli_provider=dict()):
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.outlooks = []
        self.issue = None
        self.expire = None
        self.set_metadata()
        self.find_issue_expire()
        self.find_outlooks()

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
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111)
            ax.plot(CONUS[:, 0], CONUS[:, 1], color='b', label='Conus')
            for poly in outlook.geometry:
                patch = PolygonPatch(poly, fc='r', label='Outlook')
                ax.add_patch(patch)
            ax.set_title('Category %s Threshold %s' % (outlook.category,
                                                       outlook.threshold))
            ax.legend(loc=3)
            fn = '/tmp/%s_%s_%s.png' % (self.issue.strftime("%Y%m%d%H%M"),
                                        outlook.category, outlook.threshold)
            print(':: creating plot %s' % (fn,))
            fig.savefig(fn)
            del fig
            del ax

    def set_metadata(self):
        """
        Set some metadata about this product
        """
        if self.afos == 'PTSDY1':
            self.day = '1'
            self.outlook_type = 'C'
        elif self.afos == "PTSDY2":
            self.day = '2'
            self.outlook_type = 'C'
        elif self.afos == "PTSDY3":
            self.day = '3'
            self.outlook_type = 'C'
        elif self.afos == "PTSD48":
            self.day = '4'
            self.outlook_type = 'C'
        elif self.afos == "PFWFD1":
            self.day = '1'
            self.outlook_type = 'F'
        elif self.afos == "PFWFD2":
            self.day = '2'
            self.outlook_type = 'F'
        elif self.afos == "PFWF38":
            self.day = '3'
            self.outlook_type = 'F'

    def find_issue_expire(self):
        """
        Determine the period this product is valid for
        """
        tokens = re.findall("VALID TIME ([0-9]{6})Z - ([0-9]{6})Z", self.text)
        day1 = int(tokens[0][0][:2])
        hour1 = int(tokens[0][0][2:4])
        min1 = int(tokens[0][0][4:])
        day2 = int(tokens[0][1][:2])
        hour2 = int(tokens[0][1][2:4])
        min2 = int(tokens[0][1][4:])
        issue = self.valid.replace(day=day1, hour=hour1, minute=min1)
        expire = self.valid.replace(day=day2, hour=hour2, minute=min2)
        if day1 < self.valid.day and day1 == 1:
            issue = self.valid + datetime.timedelta(days=25)
            issue = issue.replace(day=day1, hour=hour1, minute=min1)
        if day2 < self.valid.day and day2 == 1:
            expire = self.valid + datetime.timedelta(days=25)
            expire = expire.replace(day=day2, hour=hour1, minute=min1)
        self.issue = issue
        self.expire = expire

    def find_outlooks(self):
        """ Find the outlook sections within the text product! """
        if self.text.find("&&") == -1:
            self.warnings.append("Product contains no &&, adding...")
            self.text = self.text.replace("\n... ", "\n&&\n... ")
            self.text += "\n&& "
        for segment in self.text.split("&&")[:-1]:
            # We need to figure out the probabilistic or category
            tokens = re.findall("\.\.\. (.*) \.\.\.", segment)
            if len(tokens) == 0:
                continue
            category = tokens[0].strip()
            point_data = {}
            # Now we loop over the lines looking for data
            threshold = None
            for line in segment.split("\n"):
                if re.match(("^(D[3-8]\-?[3-8]?|EXTM|MRGL|ENH|SLGT|MDT|"
                             "HIGH|CRIT|TSTM|SIGN|0\.[0-9][0-9]) "),
                            line) is not None:
                    newthreshold = line.split()[0]
                    if threshold is not None and threshold == newthreshold:
                        point_data[threshold] += " 99999999 "
                    threshold = newthreshold
                if threshold is None:
                    continue
                if threshold not in point_data:
                    point_data[threshold] = ""
                point_data[threshold] += line.replace(threshold, " ")

            for threshold in point_data:
                print(("==== Category: '%s' Threshold; '%s' ====="
                       ) % (category, threshold))
                mp = str2multipolygon(point_data[threshold])
                self.outlooks.append(SPCOutlook(category, threshold, mp))

    def compute_wfos(self, txn):
        """Figure out which WFOs are impacted by this polygon"""
        for outlook in self.outlooks:
            sql = """
                select distinct wfo from ugcs WHERE
                st_contains(ST_geomFromEWKT('SRID=4326;%s'), centroid) and
                substr(ugc,3,1) = 'C' and wfo is not null
                and end_ts is null ORDER by wfo ASC
            """ % (outlook.geometry.wkt,)

            txn.execute(sql)
            for row in txn.fetchall():
                outlook.wfos.append(row['wfo'])
            print(("Category: %s Threshold: %s  #WFOS: %s %s"
                   ) % (outlook.category, outlook.threshold,
                        len(outlook.wfos), ",".join(outlook.wfos)))

    def sql(self, txn):
        """Do database work

        Args:
          txn (psycopg2.cursor): database cursor
        """
        txn.execute("""
            DELETE from spc_outlooks where valid = %s
            and expire = %s and outlook_type = %s and day = %s
        """, (self.valid, self.expire, self.outlook_type, self.day))
        if txn.rowcount > 0:
            print(("Removed %s previous spc_outlook entries"
                   ) % (txn.rowcount, ))

        for outlook in self.outlooks:
            sql = """
                INSERT into spc_outlooks(issue, valid, expire,
                threshold, category, day, outlook_type, geom)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            args = (self.issue, self.valid, self.expire,
                    outlook.threshold, outlook.category, self.day,
                    self.outlook_type,
                    "SRID=4326;%s" % (outlook.geometry.wkt,))
            txn.execute(sql, args)

    def get_descript_and_url(self):
        """Helper to convert awips id into strings"""
        product_descript = "((%s))" % (self.afos, )
        url = "http://www.spc.noaa.gov"

        if self.afos == "PTSDY1":
            product_descript = "Day 1 Convective"
            url = ("http://www.spc.noaa.gov/products/outlook/archive/"
                   "%s/day1otlk_%s.html"
                   ) % (self.valid.year, self.issue.strftime("%Y%m%d_%H%M"))
        elif self.afos == "PTSDY2":
            product_descript = "Day 2 Convective"
            url = ("http://www.spc.noaa.gov/products/outlook/archive/"
                   "%s/day2otlk_%s.html"
                   ) % (self.valid.year, self.issue.strftime("%Y%m%d_%H%M"))
        elif self.afos == "PTSDY3":
            product_descript = "Day 3 Convective"
            url = ("http://www.spc.noaa.gov/products/outlook/archive/%s/"
                   "day3otlk_%s.html") % (self.valid.year,
                                          self.issue.strftime("%Y%m%d_%H%M"))
        elif self.afos == "PTSD48":
            product_descript = "Day 4-8 Convective"
            url = ("http://www.spc.noaa.gov/products/exper/day4-8/archive/%s/"
                   "day4-8_%s.html") % (self.valid.year,
                                        self.issue.strftime("%Y%m%d_%H%M"))
        elif self.afos == "PFWFD1":
            product_descript = "Day 1 Fire"
            url = ("http://www.spc.noaa.gov/products/fire_wx/%s/"
                   "%s.html") % (self.valid.year,
                                 self.issue.strftime("%Y%m%d"))
        elif self.afos == "PFWFD2":
            product_descript = "Day 2 Fire"
            url = ("http://www.spc.noaa.gov/products/fire_wx/%s/%s.html"
                   ) % (self.valid.year, self.issue.strftime("%Y%m%d"))
        elif self.afos == "PFWF38":
            product_descript = "Day 3-8 Fire"
            url = ("http://www.spc.noaa.gov/products/fire_wx/%s/%s.html"
                   ) % (self.valid.year, self.issue.strftime("%Y%m%d"))

        return product_descript, url

    def get_jabbers(self, uri, uri2=None):
        """Figure out the jabber messaging"""
        wfos = {'TSTM': [], 'EXTM': [], 'MRGL': [], 'SLGT': [], 'ENH': [],
                'CRIT': [], 'MDT': [], 'HIGH': []}

        for outlook in self.outlooks:
            _d = wfos.setdefault(outlook.threshold, [])
            _d.extend(outlook.wfos)

        product_descript, url = self.get_descript_and_url()
        codes = {'MRGL': 'Marginal', 'SLGT': "Slight", 'ENH': 'Enhanced',
                 'MDT': "Moderate", 'HIGH': 'High',
                 'CRIT': 'Critical', 'EXTM': 'Extreme'}

        wfomsgs = {}
        for cat in ['MRGL', 'SLGT', 'ENH', 'MDT', 'HIGH', 'CRIT', 'EXTM']:
            for wfo in wfos[cat]:
                wfomsgs[wfo] = [
                    ("The Storm Prediction Center issues Day %s %s "
                     "risk for portions of %s %s") % (self.day, cat, wfo, url),
                    ("<p>The Storm Prediction Center issues "
                     "<a href=\"%s\">%s %s Risk</a> for portions "
                     "of %s's area</p>"
                     ) % (url, product_descript, codes[cat], wfo),
                    {'channels': wfo,
                     'product_id': self.get_product_id(),
                     'twitter': "SPC issues Day 1 %s risk for %s" % (cat, wfo)
                     }
                ]
        keys = wfomsgs.keys()
        keys.sort()
        res = []
        for wfo in keys:
            res.append(wfomsgs[wfo])

        # Generic for SPC
        res.append([
            ("The Storm Prediction Center issues %s Outlook"
             ) % (product_descript, ),
            ("<p>The Storm Prediction Center issues <a href=\"%s\">%s Outlook"
             "</a></p>"
             ) % (url, product_descript),
            {'channels': 'SPC',
             'product_id': self.get_product_id()
             }])
        return res


def parser(text):
    """Parse this text!"""
    return SPCPTS(text)
