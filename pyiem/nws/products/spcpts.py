"""
 Something to deal with SPC PTS Product
 My life was not supposed to end like this, what a brutal format
"""
from __future__ import print_function
import re
import datetime
import copy
import os
import itertools

import numpy as np
from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely.geometry.polygon import LinearRing
from pyiem.nws.product import TextProduct
from pyiem.util import utc

CONUS_BASETIME = utc(2019, 5, 9, 16)
CONUS = {'line': None, 'poly': None}
DAYRE = re.compile(r"SEVERE WEATHER OUTLOOK POINTS DAY\s+(?P<day>[0-9])",
                   re.IGNORECASE)
DMATCH = re.compile(r"D(?P<day1>[0-9])\-?(?P<day2>[0-9])?")

THRESHOLD2TEXT = {
    'MRGL': 'Marginal', 'SLGT': "Slight", 'ENH': 'Enhanced',
    'MDT': "Moderate", 'HIGH': 'High',
    'IDRT': 'Isolated Dry Thunderstorm',
    'SDRT': 'Scattered Dry Thunderstorm',
    'ELEV': "Elevated", 'CRIT': 'Critical', 'EXTM': 'Extreme'}
THRESHOLD_ORDER = ['0.02', '0.05', '0.10', '0.15', '0.25',
                   '0.30', '0.35', '0.40', '0.45', '0.60',
                   'TSTM', 'MRGL', 'SLGT', 'ENH', 'MDT', 'HIGH',
                   'IDRT', 'SDRT', 'ELEV', 'CRIT', 'EXTM']


def compute_times(afos, issue, expire, day):
    """compute actual issue, expire time.

    For the multi-day products, the text product contains a range of dates
    that need translated to an actual issue and expire time.

    Returns:
      issue (datetime)
      expire (datetime)
    """
    if afos not in ['PTSD48', 'PFWF38']:
        return issue, expire
    baseday = 3 if afos == 'PFWF38' else 4
    issue = issue + datetime.timedelta(days=(day - baseday))
    return issue, issue + datetime.timedelta(hours=24)


def get_day(text):
    """Figure out which day this is for"""
    search = DAYRE.search(text)
    if search is None:
        return None
    return int(search.groupdict()['day'])


def load_conus_data(valid):
    """ Load up the conus datafile for our perusal """
    fn = "%s/../../data/conus_marine_bnds%s.txt" % (
        os.path.dirname(__file__),
        "_pre190509" if valid < CONUS_BASETIME else '')
    lons = []
    lats = []
    for line in open(fn):
        tokens = line.split(",")
        lons.append(float(tokens[0]))
        lats.append(float(tokens[1]))
    CONUS['line'] = np.column_stack([lons, lats])
    CONUS['poly'] = Polygon(CONUS['line'])


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
    if pts:
        segments.append(pts)

    return segments


def clean_segment(segment):
    """Attempt to get this segment cleaned up.

    Args:
      segment (list): inbound data

    Returns:
      segment (list)
    """
    # Intersect this segment with the CONUS, if we get one segment back, done
    ls = LineString(segment)
    newls = ls.intersection(CONUS['poly'])
    if newls.is_empty:
        print("     intersection yielded empty geom, uh oh")
        return segment
    if newls.geom_type == 'LineString':
        print("     segment intersection with CONUS yielded one segment")
        return list(zip(*newls.xy))

    # We have work to do, first trim back the original segment
    segment[0] = [newls.geoms[0].xy[0][0], newls.geoms[0].xy[1][0]]
    segment[-1] = [newls.geoms[-1].xy[0][-1], newls.geoms[-1].xy[1][-1]]
    # run the intersection again!
    ls = LineString(segment)
    newls = ls.intersection(CONUS['poly'])
    if newls.geom_type == 'LineString':
        print("     trimmed segment intersection with CONUS yielded one seg")
        return list(zip(*newls.xy))

    # compute the lengths
    lengths = [g.length for g in newls.geoms]
    # if all lengths over 2, abort
    if min(lengths) > 2:
        print("     throwing up hands as segments length over 2 each")
        return segment
    maxi = lengths.index(max(lengths))

    print("     taking the longest segment as the truth")
    return list(zip(*newls.geoms[maxi].xy))


def str2multipolygon(s):
    """Convert string PTS data into a polygon.

    Args:
      s (str): the cryptic string that we attempt to make valid polygons from
    """
    segments = get_segments_from_text(s)

    # Simple case whereby the segment is its own circle, thank goodness
    if (len(segments) == 1 and
            segments[0][0][0] == segments[0][-1][0] and
            segments[0][0][1] == segments[0][-1][1]):
        print('Single closed polygon found, done and done')
        return MultiPolygon([Polygon(segments[0])])

    # Slightly bad line-work, whereby the start and end points are very close
    # to each other
    if (len(segments) == 1 and
        ((segments[0][0][0] - segments[0][-1][0])**2 +
         (segments[0][0][1] - segments[0][-1][1])**2)**0.5 < 0.05):
        print(("assuming linework error, begin: (%.2f %.2f) end: (%.2f %.2f)"
               ) % (segments[0][0][0], segments[0][0][1],
                    segments[0][-1][0], segments[0][-1][1]))
        segments[0][-1] = segments[0][0]
        return MultiPolygon([Polygon(segments[0])])

    # We start with just a conus polygon and we go from here, down the rabbit
    # hole
    polys = [copy.deepcopy(CONUS['poly']), ]

    for i, segment in enumerate(segments):
        print(('  Iterate: %s/%s, len(segment): %s (%.2f %.2f) (%.2f %.2f)'
               ) % (i+1, len(segments), len(segment), segment[0][0],
                    segment[0][1], segment[-1][0], segment[-1][1]))
        if segment[0] == segment[-1] and len(segment) > 2:
            print('     segment %s is closed polygon!' % (i,))
            lr = LinearRing(LineString(segment))
            if not lr.is_ccw:
                print('     polygon is counter-clockwise (exterior)')
                polys.insert(0, Polygon(segment))
                continue
            print("     polygon is clockwise (interior), computing which")
            found = False
            for j, poly in enumerate(polys):
                if poly.intersection(lr):
                    interiors = [l for l in polys[j].interiors]
                    interiors.append(lr)
                    newp = Polygon(polys[j].exterior, interiors)
                    if newp.is_valid:
                        polys[j] = newp
                        print(("     polygon is interior to polys #%s, "
                               "area now %.2f") % (j, polys[j].area))
                    else:
                        raise Exception(('Adding interior polygon resulted '
                                         'in an invalid geometry, aborting'))
                    found = True
                    break
            if not found:
                print('      ERROR: did not find intersection!')
            continue

        # Attempt to 'clean' this string against the CONUS Polygon
        segment = clean_segment(segment)
        ls = LineString(segment)
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
            for q in list(range(5)):
                # Compute the intersection points of this segment and what
                # is left of the pie
                (x, y) = poly.exterior.xy
                pie = np.array(list(zip(x, y)))
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
                    print('     CASE 2 idx1:%s idx2:%s' % (idx1, idx2))
                    tmpline = np.concatenate([line, pie[idx2:idx1]])
                    newpoly = Polygon(tmpline)
                    if not newpoly.is_valid:
                        print("    newpolygon is not valid, buffer(0) called ")
                        newpoly = newpoly.buffer(0)
                    polys.append(newpoly)
                    print(("     + adding polygon index: %s area: %.2f "
                           "isvalid: %s"
                           ) % (len(polys) - 1, polys[-1].area,
                                polys[-1].is_valid))
                # It is possible that our line start and end points are closest
                # to the same point on the pie.
                else:
                    # just inject the point into the line
                    tmpline = np.concatenate([line, [pie[idx2], ]])
                    newpoly = Polygon(tmpline)
                    if not newpoly.is_valid:
                        print("    newpolygon is not valid, buffer(0) called ")
                        newpoly = newpoly.buffer(0)
                    polys.append(newpoly)
                    print(("     + adding polygon index: %s area: %.2f "
                           "isvalid: %s"
                           ) % (len(polys) - 1, polys[-1].area,
                                polys[-1].is_valid))
                print("     breaking out of q loop")
                break

        if not found:
            print('     segment did not intersect')

    res = []
    print(('  Resulted in len(polys): %s, now quality controlling'
           ) % (len(polys),))
    for i, poly in enumerate(polys):
        if not poly.is_valid:
            print('     ERROR: polygon %s is invalid!' % (i,))
            continue
        if poly.area == CONUS['poly'].area:
            print('     polygon %s is just CONUS, skipping' % (i,))
            continue
        print('     polygon: %s has area: %s' % (i, poly.area))
        res.append(poly)
    if not res:
        raise Exception(("Processed no geometries, this is a bug!\n"
                         "  s is %s\n"
                         "  segments is %s" % (repr(s), repr(segments))))
    return MultiPolygon(res)


class SPCOutlookCollection(object):
    """ A collection of outlooks for a single 'day'"""

    def __init__(self, issue, expire, day):
        """Constructor"""
        self.issue = issue
        self.expire = expire
        self.day = day
        self.outlooks = []


class SPCOutlook(object):
    """A class holding what we store for a single outlook."""

    def __init__(self, category, threshold, multipoly):
        """Constructor.

        Args:
          category (str): the label of this category
          threshold (str): the threshold associated with the category
          multipoly (MultiPolygon): the geometry
        """
        self.category = category
        self.threshold = threshold
        self.geometry = multipoly
        self.wfos = []


class SPCPTS(TextProduct):
    """A class representing the polygons and metadata in SPC PTS Product"""

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        """Constructor

        Args:
          text (string): the raw PTS product that is to be parsed
          utcnow (datetime, optional): in case of ambuigity with time
          ugc_provider (dict, optional): unused in this class
          nwsli_provider (dict, optional): unused in this class
        """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        print("==== SPCPTS Processing: %s" % (self.get_product_id(), ))
        load_conus_data(self.valid)
        self.issue = None
        self.expire = None
        self.day = None
        self.outlook_type = None
        self.outlook_collections = dict()
        self.set_metadata()
        self.find_issue_expire()
        self.find_outlooks()
        self.quality_control()

    def quality_control(self):
        """Run some checks against what was parsed"""
        # 1. Do polygons overlap for the same outlook
        print("==== Running Quality Control Checks")
        for day, collect in self.outlook_collections.items():
            # Everything should be smaller than General Thunder, for conv
            tstm = self.get_outlook('CATEGORICAL', 'TSTM', day)
            for outlook in collect.outlooks:
                rewrite = False
                # case of single polygon
                if tstm and len(outlook.geometry) == 1:
                    if outlook.geometry.area > tstm.geometry.area:
                        rewrite = True
                        msg = ("Discarding polygon as it is larger than TSTM: "
                               "Day: %s %s %s Area: %.2f"
                               ) % (day, outlook.category, outlook.threshold,
                                    outlook.geometry.area)
                        print(msg)
                        self.warnings.append(msg)
                # clip polygons to the CONUS
                good_polys = []
                for poly in outlook.geometry:
                    good_polys.append(CONUS['poly'].intersection(poly))
                outlook.geometry = MultiPolygon(good_polys)

                good_polys = []
                for poly1, poly2 in itertools.permutations(outlook.geometry,
                                                           2):
                    if poly1.contains(poly2):
                        rewrite = True
                        msg = ("Discarding exterior polygon: "
                               "Day: %s %s %s Area: %.2f"
                               ) % (day, outlook.category, outlook.threshold,
                                    poly1.area)
                        print(msg)
                        self.warnings.append(msg)
                    elif tstm is not None and poly1.area > tstm.geometry.area:
                        rewrite = True
                        msg = ("Discarding polygon as it is larger than TSTM: "
                               "Day: %s %s %s Area: %.2f"
                               ) % (day, outlook.category, outlook.threshold,
                                    poly1.area)
                        print(msg)
                        self.warnings.append(msg)
                    else:
                        good_polys.append(poly1)
                if rewrite:
                    outlook.geometry = MultiPolygon(good_polys)
        # 2. Do the time bounds make sense, limited scope here
        if (self.day == 1 and
                (self.issue - self.valid).total_seconds() > 8 * 3600):
            self.warnings.append((
                "time_bounds_check: day: %s issue: %s valid: %s expire: %s"
                ) % (self.day, self.issue, self.valid, self.expire)
            )

    def get_outlookcollection(self, day):
        """Returns the SPCOutlookCollection for a given day"""
        return self.outlook_collections.get(day)

    def get_outlook(self, category, threshold, day=None):
        ''' Get an outlook by category and threshold '''
        if not self.outlook_collections:
            return None
        if day is None:
            day = self.day
        if day not in self.outlook_collections:
            return None
        for outlook in self.outlook_collections[day].outlooks:
            if outlook.category == category and outlook.threshold == threshold:
                return outlook
        return None

    def draw_outlooks(self):
        ''' For debugging, draw the outlooks on a simple map for inspection!'''
        from descartes.patch import PolygonPatch
        import matplotlib.pyplot as plt
        for day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
                fig = plt.figure(figsize=(12, 8))
                ax = fig.add_subplot(111)
                # pylint: disable=unsubscriptable-object
                ax.plot(CONUS['line'][:, 0], CONUS['line'][:, 1],
                        color='b', label='Conus')
                for poly in outlook.geometry:
                    patch = PolygonPatch(poly, fc='tan', label='Outlook',
                                         zorder=2)
                    ax.add_patch(patch)
                    ax.plot(poly.exterior.xy[0],
                            poly.exterior.xy[1], lw=2, color='r')
                ax.set_title(('Day %s Category %s Threshold %s'
                              ) % (day, outlook.category, outlook.threshold))
                ax.legend(loc=3)
                fn = (('/tmp/%s_%s_%s_%s.png'
                       ) % (day, self.issue.strftime("%Y%m%d%H%M"),
                            outlook.category, outlook.threshold)).replace(" ",
                                                                          "_")
                print(':: creating plot %s' % (fn,))
                fig.savefig(fn)
                del fig
                del ax

    def set_metadata(self):
        """
        Set some metadata about this product
        """
        if self.afos == 'PTSDY1':
            self.day = 1
            self.outlook_type = 'C'
        elif self.afos == "PTSDY2":
            self.day = 2
            self.outlook_type = 'C'
        elif self.afos == "PTSDY3":
            self.day = 3
            self.outlook_type = 'C'
        elif self.afos == "PTSD48":
            self.outlook_type = 'C'
        elif self.afos == "PFWFD1":
            self.day = 1
            self.outlook_type = 'F'
        elif self.afos == "PFWFD2":
            self.day = 2
            self.outlook_type = 'F'
        elif self.afos == "PFWF38":
            self.outlook_type = 'F'
        else:
            self.warnings.append(("Unknown awipsid '%s' for metadata"
                                  ) % (self.afos, ))

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
        # NB: outlooks can go out more than just one day
        if day1 < self.valid.day:
            issue = self.valid + datetime.timedelta(days=25)
            issue = issue.replace(day=day1, hour=hour1, minute=min1)
        if day2 < self.valid.day:
            expire = self.valid + datetime.timedelta(days=25)
            expire = expire.replace(day=day2, hour=hour2, minute=min2)
        self.issue = issue
        self.expire = expire

    def find_outlooks(self):
        """ Find the outlook sections within the text product! """
        if self.text.find("&&") == -1:
            self.warnings.append("Product contains no &&, adding...")
            self.text = self.text.replace("\n... ", "\n&&\n... ")
            self.text += "\n&& "
        for segment in self.text.split("&&")[:-1]:
            day = self.day
            if day is None:
                day = get_day(segment)
            # We need to figure out the probabilistic or category
            tokens = re.findall(r"\.\.\.\s+(.*)\s+\.\.\.", segment)
            if not tokens:
                continue
            category = tokens[0].strip()
            point_data = {}
            # Now we loop over the lines looking for data
            threshold = None
            for line in segment.split("\n"):
                if re.match((r"^(D[3-8]\-?[3-8]?|EXTM|MRGL|ENH|SLGT|MDT|ELEV|"
                             r"HIGH|CRIT|TSTM|SIGN|IDRT|SDRT|0\.[0-9][0-9]) "),
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

            if day is not None:
                issue, expire = compute_times(
                    self.afos, self.issue, self.expire, day)
                collect = self.outlook_collections.setdefault(
                    day, SPCOutlookCollection(issue, expire, day))
            # We need to duplicate, in the case of day-day spans
            for threshold in list(point_data.keys()):
                if threshold == 'TSTM' and self.afos == 'PFWF38':
                    print(("Failing to parse TSTM in PFWF38"))
                    del point_data[threshold]
                    continue
                match = DMATCH.match(threshold)
                if match:
                    data = match.groupdict()
                    if data.get('day2') is not None:
                        day1 = int(data['day1'])
                        day2 = int(data['day2'])
                        print("Duplicating threshold %s-%s" % (day1, day2))
                        for i in range(day1, day2 + 1):
                            key = "D%s" % (i,)
                            point_data[key] = point_data[threshold]
                        del point_data[threshold]
            for threshold in point_data:
                match = DMATCH.match(threshold)
                if match:
                    day = int(match.groupdict()['day1'])
                    issue, expire = compute_times(
                        self.afos, self.issue, self.expire, day)
                    collect = self.outlook_collections.setdefault(
                        day, SPCOutlookCollection(issue, expire, day))
                print(("--> Start Day: %s Category: '%s' Threshold: '%s' ====="
                       ) % (day, category, threshold))
                mp = str2multipolygon(point_data[threshold])
                if DMATCH.match(threshold):
                    threshold = '0.15'
                print(("----> End threshold is: %s" % (threshold, )))
                collect.outlooks.append(SPCOutlook(category, threshold, mp))

    def compute_wfos(self, txn):
        """Figure out which WFOs are impacted by this polygon"""
        for day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
                if outlook.geometry.is_empty:
                    continue
                sql = """
                    select distinct wfo from ugcs WHERE
                    st_contains(ST_geomFromEWKT('SRID=4326;%s'), centroid) and
                    substr(ugc,3,1) = 'C' and wfo is not null
                    and end_ts is null ORDER by wfo ASC
                """ % (outlook.geometry.wkt,)

                txn.execute(sql)
                for row in txn.fetchall():
                    outlook.wfos.append(row['wfo'])
                print(("Day: %s Category: %s Threshold: %s #WFOS: %s %s"
                       ) % (day, outlook.category, outlook.threshold,
                            len(outlook.wfos), ",".join(outlook.wfos)))

    def sql(self, txn):
        """Do database work

        Args:
          txn (psycopg2.cursor): database cursor
        """
        for day, collect in self.outlook_collections.items():
            txn.execute("""
                DELETE from spc_outlooks where product_issue = %s
                and expire = %s and outlook_type = %s and day = %s
            """, (self.valid, self.expire, self.outlook_type, day))
            if txn.rowcount > 0:
                print(("Removed %s previous spc_outlook entries"
                       ) % (txn.rowcount, ))

            for outlook in collect.outlooks:
                if outlook.geometry.is_empty:
                    continue
                sql = """
                    INSERT into spc_outlooks(product_issue, issue, expire,
                    threshold, category, day, outlook_type, geom)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                args = (self.valid, collect.issue, collect.expire,
                        outlook.threshold, outlook.category, collect.day,
                        self.outlook_type,
                        "SRID=4326;%s" % (outlook.geometry.wkt,))
                txn.execute(sql, args)

    def get_descript_and_url(self):
        """Helper to convert awips id into strings"""
        product_descript = "((%s))" % (self.afos, )
        url = "http://www.spc.noaa.gov"
        day = "((%s))" % (self.afos,)

        if self.afos == "PTSDY1":
            day = 'Day 1'
            product_descript = "Convective"
            url = ("https://www.spc.noaa.gov/products/outlook/archive/"
                   "%s/day1otlk_%s.html"
                   ) % (self.valid.year, self.issue.strftime("%Y%m%d_%H%M"))
        elif self.afos == "PTSDY2":
            day = 'Day 2'
            product_descript = "Convective"
            hhmm = "1730" if self.valid.hour > 11 else '0600'
            url = ("https://www.spc.noaa.gov/products/outlook/archive/"
                   "%s/day2otlk_%s_%s.html"
                   ) % (self.valid.year, self.valid.strftime("%Y%m%d"), hhmm)
        elif self.afos == "PTSDY3":
            # 0730 when in CDT, 0830 when in CST
            hhmm = '0730' if self.z == 'CDT' else '0830'
            day = 'Day 3'
            product_descript = "Convective"
            url = ("https://www.spc.noaa.gov/products/outlook/archive/%s/"
                   "day3otlk_%s_%s.html") % (self.valid.year,
                                             self.valid.strftime("%Y%m%d"),
                                             hhmm)
        elif self.afos == "PTSD48":
            day = 'Days 4-8'
            product_descript = "Convective"
            url = ("https://www.spc.noaa.gov/products/exper/day4-8/archive/%s/"
                   "day4-8_%s.html") % (self.valid.year,
                                        self.valid.strftime("%Y%m%d"))
        elif self.afos == "PFWFD1":
            day = 'Day 1'
            product_descript = "Fire Weather"
            url = self.issue.strftime(
                ("https://www.spc.noaa.gov/products/fire_wx/%Y/%y%m%d_%H%M"
                 "_fwdy1_print.html")
            )
        elif self.afos == "PFWFD2":
            day = 'Day 2'
            product_descript = "Fire Weather"
            url = self.issue.strftime(
                ("https://www.spc.noaa.gov/products/fire_wx/%Y/%y%m%d_%H%M"
                 "_fwdy2_print.html")
            )
        elif self.afos == "PFWF38":
            day = 'Day 3-8'
            product_descript = "Fire Weather"
            url = self.issue.strftime(
                ("https://www.spc.noaa.gov/products/exper/fire_wx/%Y/%y%m%d"
                 ".html")
            )

        return product_descript, url, day

    def get_jabbers(self, uri, uri2=None):
        """Wordsmith the Jabber/Twitter Messaging

        Examples
        --------
          The Storm Prediction Center issues Day 1 Convective Outlook
            at 16z 6 April
          The Storm Prediction Center issues Day 1 Moderate Risk at 16z 6 Apr
            for portions of DMX
          SPC issues Day 1 Moderate Risk at 16z 6 April for #DMX
        """
        res = []
        product_descript, url, title = self.get_descript_and_url()
        jdict = {
            'title': title,
            'name': 'The Storm Prediction Center',
            'tstamp': self.valid.strftime("%b %-d, %-H:%Mz"),
            'outlooktype': product_descript,
            'url': url
            }
        for _, collect in self.outlook_collections.items():

            wfos = {'TSTM': [], 'EXTM': [], 'MRGL': [], 'SLGT': [], 'ENH': [],
                    'CRIT': [], 'MDT': [], 'HIGH': [], 'ELEV': [],
                    'IDRT': [], 'SDRT': []}

            for outlook in collect.outlooks:
                _d = wfos.setdefault(outlook.threshold, [])
                _d.extend(outlook.wfos)

            jdict['day'] = collect.day
            wfomsgs = {}
            # We order in least to greatest, so that the highest threshold
            # overwrites lower ones
            for cat in ['MRGL', 'SLGT', 'ENH', 'MDT', 'HIGH',
                        'ELEV', 'CRIT', 'EXTM', 'IDRT', 'SDRT']:
                jdict['ttext'] = "%s %s Risk" % (THRESHOLD2TEXT[cat],
                                                 product_descript)
                for wfo in wfos[cat]:
                    jdict['wfo'] = wfo
                    wfomsgs[wfo] = [
                        ("%(name)s issues Day %(day)s %(ttext)s "
                         "at %(tstamp)s for portions of %(wfo)s %(url)s"
                         ) % jdict,
                        ("<p>%(name)s issues "
                         "<a href=\"%(url)s\">Day %(day)s %(ttext)s</a> "
                         "at %(tstamp)s for portions of %(wfo)s's area</p>"
                         ) % jdict,
                        {'channels': wfo,
                         'product_id': self.get_product_id(),
                         'twitter': ("SPC issues Day %(day)s %(ttext)s "
                                     "at %(tstamp)s for %(wfo)s %(url)s"
                                     ) % jdict
                         }
                    ]
            keys = list(wfomsgs.keys())
            keys.sort()
            res = []
            for wfo in keys:
                res.append(wfomsgs[wfo])

        # Generic for SPC
        res.append([
            ("%(name)s issues %(title)s %(outlooktype)s Outlook at %(tstamp)s"
             " %(url)s"
             ) % jdict,
            ("<p>%(name)s issues <a href=\"%(url)s\">%(title)s "
             "%(outlooktype)s Outlook</a> at %(tstamp)s</p>"
             ) % jdict,
            {'channels': 'SPC',
             'product_id': self.get_product_id(),
             'twitter': ("%(name)s issues %(title)s "
                         "%(outlooktype)s Outlook at %(tstamp)s %(url)s"
                         ) % jdict
             }])
        return res


def parser(text, utcnow=None):
    """Parse this text!"""
    return SPCPTS(text, utcnow)
