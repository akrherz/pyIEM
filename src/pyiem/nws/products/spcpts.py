"""
 Something to deal with SPC PTS Product
 My life was not supposed to end like this, what a brutal format
"""
import re
import datetime
import copy
import os
import itertools

import numpy as np
from shapely.geometry import (
    Polygon,
    LineString,
    MultiPolygon,
    Point,
    MultiLineString,
)
from shapely.geometry.collection import GeometryCollection
from shapely.geometry.polygon import LinearRing
from shapely.affinity import translate

# Local
from pyiem.geom_util import rhs_split
from pyiem.nws.product import TextProduct
from pyiem.util import utc, LOG, load_geodf

CONUS_BASETIME = utc(2019, 5, 9, 16)
CONUS = {"line": None, "poly": None}
DAYRE = re.compile(
    r"SEVERE WEATHER OUTLOOK POINTS DAY\s+(?P<day>[0-9])", re.IGNORECASE
)
DMATCH = re.compile(r"D(?P<day1>[0-9])\-?(?P<day2>[0-9])?")

THRESHOLD2TEXT = {
    "MRGL": "Marginal",
    "SLGT": "Slight",
    "ENH": "Enhanced",
    "MDT": "Moderate",
    "HIGH": "High",
    "IDRT": "Isolated Dry Thunderstorm",
    "SDRT": "Scattered Dry Thunderstorm",
    "ELEV": "Elevated",
    "CRIT": "Critical",
    "EXTM": "Extreme",
}
THRESHOLD_ORDER = [
    "0.02",
    "0.05",
    "0.10",
    "0.15",
    "0.25",
    "0.30",
    "0.35",
    "0.40",
    "0.45",
    "0.60",
    "TSTM",
    "MRGL",
    "SLGT",
    "ENH",
    "MDT",
    "HIGH",
    "IDRT",
    "SDRT",
    "ELEV",
    "CRIT",
    "EXTM",
]


def compute_times(afos, issue, expire, day):
    """compute actual issue, expire time.

    For the multi-day products, the text product contains a range of dates
    that need translated to an actual issue and expire time.

    Returns:
      issue (datetime)
      expire (datetime)
    """
    if afos not in ["PTSD48", "PFWF38"]:
        return issue, expire
    baseday = 3 if afos == "PFWF38" else 4
    issue = issue + datetime.timedelta(days=(day - baseday))
    return issue, issue + datetime.timedelta(hours=24)


def get_day(prod, text):
    """Figure out which day this is for"""
    if prod.afos in ["PTSDY1", "PTSDY2", "PTSDY3", "PFWFD1", "PFWFD2"]:
        return int(prod.afos[5])
    search = DAYRE.search(text)
    if search is None:
        return None
    return int(search.groupdict()["day"])


def load_conus_data(valid):
    """Load up the conus datafile for our perusal"""
    fn = "%s/../../data/conus_marine_bnds%s.txt" % (
        os.path.dirname(__file__),
        "_pre190509" if valid < CONUS_BASETIME else "",
    )
    lons = []
    lats = []
    with open(fn) as fh:
        for line in fh:
            tokens = line.split(",")
            lons.append(float(tokens[0]))
            lats.append(float(tokens[1]))
    CONUS["line"] = np.column_stack([lons, lats])
    CONUS["poly"] = Polygon(CONUS["line"])


def get_segments_from_text(text):
    """Return list of segments for this text"""
    tokens = re.findall("([0-9]{8})", text.replace("\n", ""))
    # First we generate a list of segments, based on what we found
    segments = []
    pts = []
    for token in tokens:
        lat = float(token[:4]) / 100.0
        lon = 0 - (float(token[-4:]) / 100.0)
        if lon > -30:
            lon -= 100.0
        if token == "99999999":
            if len(pts) > 1:
                segments.append(pts)
            pts = []
        else:
            pts.append([lon, lat])
    if len(pts) > 1:
        segments.append(pts)

    return segments


def ensure_outside_conus(ls):
    """Make sure the start and end of a given line are outside the CONUS."""
    # First and last point of the ls need to be exterior to the CONUS
    for idx in [0, -1]:
        pt = Point(ls.coords[idx])
        if not pt.within(CONUS["poly"]):
            continue
        pt = CONUS["poly"].exterior.interpolate(
            CONUS["poly"].exterior.project(pt)
        )
        if pt.within(CONUS["poly"]):
            LOG.info("     idx: %s is still within, evasive action", idx)
            done = False
            for multi in [0.01, 0.1, 1.0]:
                if done:
                    break
                for xoff, yoff in [
                    [-0.01 * multi, -0.01 * multi],
                    [-0.01 * multi, 0.0 * multi],
                    [-0.01 * multi, 0.01 * multi],
                    [0.0 * multi, -0.01 * multi],
                    [0.0 * multi, 0.0 * multi],
                    [0.0 * multi, 0.01 * multi],
                    [0.01 * multi, -0.01 * multi],
                    [0.01 * multi, 0.0 * multi],
                    [0.01 * multi, 0.01 * multi],
                ]:
                    pt2 = translate(pt, xoff=xoff, yoff=yoff)
                    if not pt2.within(CONUS["poly"]):
                        pt = pt2
                        LOG.info("     idx: %s is now %s", idx, pt)
                        done = True
                        break
        LOG.info(
            "     fix idx: %s to new: %.4f %.4f Inside: %s",
            idx,
            pt.x,
            pt.y,
            pt.within(CONUS["poly"]),
        )
        coords = list(ls.coords)
        coords[idx] = (pt.x, pt.y)
        ls = LineString(coords)
    return ls


def clean_segment(ls):
    """Attempt to get this segment cleaned up.

    Args:
      segment (list): inbound data

    Returns:
      segment (list)
    """
    # Make sure this is outside the CONUS
    ls = ensure_outside_conus(ls)
    # Examine how our linestring intersects the CONUS polygon
    res = ls.intersection(CONUS["poly"])
    if isinstance(res, LineString):
        LOG.info("     segment generates single line against CONUS, done")
        return ls
    # We got multiple linestrings
    LOG.info("     segment intersection yielded %s linestrings", len(res))
    res = [r for r in res if r.length > 0.2]  # arb
    if len(res) == 1:
        LOG.info("    was able to filter out very short lines")
        return ensure_outside_conus(res[0])
    LOG.info("     returning a MultiLineString")
    return MultiLineString(res)


def look_for_closed_polygon(segment):
    """Simple logic to see if our polygon is already closed."""
    if segment[0][0] == segment[-1][0] and segment[0][1] == segment[-1][1]:
        LOG.info("Single closed polygon found, done and done")
        poly = Polygon(segment)
        if not poly.is_valid:
            LOG.info("closed polygon is invalid, buffer(0) to the rescue.")
            poly = poly.buffer(0)
        return MultiPolygon([poly])

    # Slightly bad line-work, whereby the start and end points are very close
    # to each other
    if (
        (segment[0][0] - segment[-1][0]) ** 2
        + (segment[0][1] - segment[-1][1]) ** 2
    ) ** 0.5 < 0.05:
        LOG.info(
            "assuming linework error, begin: (%.2f %.2f) end: (%.2f %.2f)",
            segment[0][0],
            segment[0][1],
            segment[-1][0],
            segment[-1][1],
        )
        segment[-1] = segment[0]
        return MultiPolygon([Polygon(segment)])


def segment_logic(segment, currentpoly, polys):
    """Our segment parsing logic."""
    LOG.info(
        "     segment_logic currentpoly.area: %.2f len(polys): %s",
        currentpoly.area,
        len(polys),
    )
    # Perhaps our segment end points are close enough to almost touch, we
    # can finish the job!
    if segment[0] != segment[-1] and len(segment) > 2:
        dist = (
            (segment[0][0] - segment[-1][0]) ** 2
            + (segment[0][1] - segment[-1][1]) ** 2
        ) ** 0.5
        if dist < 1:  # arb
            LOG.info("     Start and end pt %.3f apart, ajoining", dist)
            segment.append(segment[0])
    if segment[0] == segment[-1] and len(segment) > 2:
        LOG.info("     segment is closed polygon!")
        lr = LinearRing(LineString(segment))
        if not lr.is_ccw:
            LOG.info("     polygon is clockwise (exterior), done.")
            polys.append(currentpoly)
            return Polygon(segment)
        LOG.info("     polygon is CCW (interior), testing intersection")
        if currentpoly.intersection(lr).is_empty:
            LOG.info("     failed intersection with currentpoly, abort")
            return currentpoly
        interiors = list(currentpoly.interiors)
        interiors.append(lr)
        newp = Polygon(currentpoly.exterior, interiors)
        if not newp.is_valid:
            LOG.info("     adding interior invalid, buffering")
            newp = newp.buffer(0)
        if newp.is_valid:
            LOG.info(
                "     polygon is interior to currentpoly, area: %.2f ",
                currentpoly.area,
            )
            return newp
        raise Exception(
            "Adding interior polygon resulted in an invalid geometry, aborting"
        )

    # All open lines need to intersect the CONUS, ensure that happens
    ls = clean_segment(LineString(segment))
    if isinstance(ls, MultiLineString):
        sz = len(ls)
        for i, _ls in enumerate(ls):
            res = segment_logic(list(_ls.coords), currentpoly, polys)
            if i < (sz - 1):
                if res.intersects(ls[i + 1]):
                    LOG.info("     next ls intersects res, keeping")
                    currentpoly = res
                else:
                    for k, poly in enumerate(polys):
                        if poly.intersects(ls[i + 1]):
                            LOG.info("     resetting currentpoly")
                            currentpoly = polys.pop(k)
                            break
                    LOG.info("     collecting up res.area: %.2f", res.area)
                    polys.append(res)
            else:
                currentpoly = res
        return currentpoly
    if ls is None:
        LOG.info("     aborting as clean_segment failed...")
        return currentpoly
    LOG.info(
        "     new segment start: %.4f %.4f end: %.4f %.4f",
        ls.coords[0][0],
        ls.coords[0][1],
        ls.coords[-1][0],
        ls.coords[-1][1],
    )

    # If this line segment does not intersect the current polygon of interest,
    # we should check any previous polygons to see if it intersects it. We
    # could be dealing with invalid ordering in the file, sigh.
    if currentpoly.intersection(ls).is_empty:
        LOG.info("     ls does not intersect currentpoly, looking for match")
        found = False
        for i, poly in enumerate(polys):
            intersect = poly.intersection(ls)
            if intersect.is_empty or isinstance(intersect, MultiLineString):
                continue
            LOG.info(
                "     found previous polygon i:%s area: %.1f that intersects",
                i,
                poly.area,
            )
            found = True
            LOG.info("     add poly.area: %.2f to polys", currentpoly.area)
            polys.append(currentpoly)
            currentpoly = polys.pop(i)
            break
        if not found:
            LOG.info("     setting currentpoly back to CONUS")
            LOG.info("     add poly.area: %.2f to polys", currentpoly.area)
            polys.append(currentpoly)
            currentpoly = copy.deepcopy(CONUS["poly"])

    newpoly = rhs_split(currentpoly, ls)
    if newpoly is None:
        LOG.info("     rhs_split yielded None, returning currentpoly?")
        return currentpoly

    LOG.info("     newpoly.area = %.4f", newpoly.area)
    return newpoly


# def debug_draw(i, segment, current_poly):
#    """Draw this for debugging purposes."""
#    segment = np.array(segment)
#    from pyiem.plot.use_agg import plt
#    (fig, ax) = plt.subplots(1, 1)
#    ax.plot(segment[:, 0], segment[:, 1], c='b')
#    ylim = ax.get_ylim()
#    xlim = ax.get_xlim()
#    ax.plot(current_poly.exterior.xy[0], current_poly.exterior.xy[1], c='r')
#    ax.set_xlim(*xlim)
#    ax.set_ylim(*ylim)
#    LOG.info(f"writting /tmp/{i}debugdraw.png")
#    fig.savefig(f"/tmp/{i}debugdraw.png")


def str2multipolygon(s):
    """Convert string PTS data into a polygon.

    Args:
      s (str): the cryptic string that we attempt to make valid polygons from
    """
    segments = get_segments_from_text(s)
    # Simple case whereby the segment is its own circle, thank goodness
    if len(segments) == 1:
        res = look_for_closed_polygon(segments[0])
        if res:
            return res

    # Keep track of generated polygons
    polys = []
    # currentpoly is our present subject of interest
    currentpoly = copy.deepcopy(CONUS["poly"])

    for i, segment in enumerate(segments):
        # debug_draw(i, segment, currentpoly)
        LOG.info(
            "  Iterate: %s/%s, len(segment): %s (%.2f %.2f) (%.2f %.2f)",
            i + 1,
            len(segments),
            len(segment),
            segment[0][0],
            segment[0][1],
            segment[-1][0],
            segment[-1][1],
        )
        currentpoly = segment_logic(segment, currentpoly, polys)
    polys.append(currentpoly)

    res = []
    LOG.info(
        "  Resulted in len(polys): %s, now quality controlling", len(polys)
    )
    for i, poly in enumerate(polys):
        if not poly.is_valid:
            LOG.info("     ERROR: polygon %s is invalid!", i)
            continue
        if poly.area == CONUS["poly"].area:
            LOG.info("     polygon %s is just CONUS, skipping", i)
            continue
        LOG.info("     polygon: %s has area: %s", i, poly.area)
        res.append(poly)
    # Look for overlapping polygons
    toadd = []
    toremove = []
    for combo in itertools.combinations(res, 2):
        if combo[0].intersects(combo[1]):
            LOG.info("     polygons intersect, differencing!")
            # Take the difference of the larger from the smaller
            i = 1
            j = 0
            if combo[0].area > combo[1].area:
                i = 0
                j = 1
            poly = combo[i].difference(combo[j])
            if isinstance(poly, MultiPolygon):
                toadd.extend([geo for geo in poly])
            else:
                toadd.append(poly)
            toremove.append(combo[0])
            toremove.append(combo[1])
    for poly in toremove:
        if poly in res:
            res.remove(poly)
    for poly in toadd:
        res.append(poly)
    if not res:
        raise Exception(
            (
                "Processed no geometries, this is a bug!\n"
                "  s is %s\n"
                "  segments is %s" % (repr(s), repr(segments))
            )
        )
    return MultiPolygon(res)


def init_days(prod):
    """Figure out which days this product should have based on the AFOS."""

    def f(day):
        """generator."""
        issue, expire = compute_times(prod.afos, prod.issue, prod.expire, day)

        return SPCOutlookCollection(issue, expire, day)

    if prod.afos == "PTSD48":
        return {4: f(4), 5: f(5), 6: f(6), 7: f(7), 8: f(8)}
    if prod.afos == "PFWF38":
        return {3: f(3), 4: f(4), 5: f(5), 6: f(6), 7: f(7), 8: f(8)}
    return {int(prod.afos[5]): f(int(prod.afos[5]))}


def _compute_cycle(prod):
    """Figure out an integer cycle that identifies this product."""
    # Extended ones are easy
    if prod.afos in ["PTSD48", "PFWF38"]:
        return 21 if prod.outlook_type == "F" else 10
    day = int(prod.afos[5])
    if day == 3:  # has to be convective
        return 8
    # Day 2 are based on the product issuance time
    if day == 2:
        if prod.outlook_type == "F":
            if prod.valid.hour in range(4, 13):
                return 8
            if prod.valid.hour in range(14, 23):
                return 18
        if prod.outlook_type == "C":
            if prod.valid.hour in range(4, 13):
                return 7
            if prod.valid.hour in range(14, 23):
                return 17
        return -1
    # We are left with day 1
    hhmi = prod.get_outlookcollection(day).issue.strftime("%H%M")
    if prod.outlook_type == "C":
        lkp = {"1200": 6, "1300": 13, "1630": 16, "2000": 20, "0100": 1}
        return lkp.get(hhmi, -1)
    lkp = {"1200": 7, "1700": 17}
    return lkp.get(hhmi, -1)


def _sql_cycle_canonical(prod, txn, day, collect, outlook_id):
    """Check our database."""
    txn.execute(
        "SELECT id, product_issue from spc_outlook where expire = %s and "
        "outlook_type = %s and day = %s and cycle = %s",
        (collect.expire, prod.outlook_type, day, prod.cycle),
    )
    if txn.rowcount == 0:  # yes
        LOG.info("Setting as canonical cycle of %s", prod.cycle)
        txn.execute(
            "UPDATE spc_outlook SET cycle = %s where id = %s",
            (prod.cycle, outlook_id),
        )
    else:
        # tricky
        is_canonical = True
        for row in txn.fetchall():
            if row["product_issue"] < prod.valid:
                txn.execute(
                    "UPDATE spc_outlook SET cycle = -1 where id = %s",
                    (row["id"],),
                )
            else:
                is_canonical = False
        txn.execute(
            "UPDATE spc_outlook SET cycle = %s where id = %s",
            (prod.cycle if is_canonical else -1, outlook_id),
        )


def _sql_day_collect(prod, txn, day, collect):
    """Do database work."""
    # Compute what our outlook identifier is
    txn.execute(
        "SELECT id from spc_outlook where product_issue = %s and "
        "day = %s and outlook_type = %s",
        (prod.valid, day, prod.outlook_type),
    )
    if txn.rowcount > 0:
        outlook_id = txn.fetchone()[0]
        # Do some deleting
        txn.execute(
            "DELETE from spc_outlook_geometries where spc_outlook_id = %s",
            (outlook_id,),
        )
        LOG.info("Removed %s rows from spc_outlook_geometries", txn.rowcount)
    else:
        txn.execute(
            "INSERT into spc_outlook(issue, product_issue, expire, product_id,"
            "outlook_type, day, cycle) VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (
                collect.issue,
                prod.valid,
                collect.expire,
                prod.get_product_id(),
                prod.outlook_type,
                day,
                -1 if prod.cycle < 0 else -2,  # Placeholder, if necessary
            ),
        )
        outlook_id = txn.fetchone()[0]
    # Now, are we the canonical outlook for this cycle?
    if prod.cycle > -1:
        _sql_cycle_canonical(prod, txn, day, collect, outlook_id)
    for outlook in collect.outlooks:
        if outlook.geometry.is_empty:
            continue
        txn.execute(
            "INSERT into spc_outlook_geometries(spc_outlook_id, "
            "threshold, category, geom) VALUES (%s, %s, %s, %s)",
            (
                outlook_id,
                outlook.threshold,
                outlook.category,
                "SRID=4326;%s" % (outlook.geometry.wkt,),
            ),
        )


class SPCOutlookCollection:
    """A collection of outlooks for a single 'day'"""

    def __init__(self, issue, expire, day):
        """Constructor"""
        self.issue = issue
        self.expire = expire
        self.day = day
        self.outlooks = []


class SPCOutlook:
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

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """Constructor

        Args:
          text (string): the raw PTS product that is to be parsed
          utcnow (datetime, optional): in case of ambuigity with time
          ugc_provider (dict, optional): unused in this class
          nwsli_provider (dict, optional): unused in this class
        """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        LOG.info("==== SPCPTS Processing: %s", self.get_product_id())
        load_conus_data(self.valid)
        self.issue = None
        self.expire = None
        self.outlook_type = None
        self.set_metadata()
        self.find_issue_expire()
        self.outlook_collections = init_days(self)
        self.find_outlooks()
        self.quality_control()
        self.compute_wfos()
        self.cycle = _compute_cycle(self)

    def quality_control(self):
        """Run some checks against what was parsed"""
        # 1. Do polygons overlap for the same outlook
        LOG.info("==== Running Quality Control Checks")
        for day, collect in self.outlook_collections.items():
            # Everything should be smaller than General Thunder, for conv
            tstm = self.get_outlook("CATEGORICAL", "TSTM", day)
            for outlook in collect.outlooks:
                rewrite = False
                # case of single polygon
                if tstm and len(outlook.geometry) == 1:
                    if outlook.geometry.area > tstm.geometry.area:
                        rewrite = True
                        msg = (
                            "Discarding polygon as it is larger than TSTM: "
                            "Day: %s %s %s Area: %.2f TSTM Area: %.2f"
                        ) % (
                            day,
                            outlook.category,
                            outlook.threshold,
                            outlook.geometry.area,
                            tstm.geometry.area,
                        )
                        LOG.info(msg)
                        self.warnings.append(msg)
                # clip polygons to the CONUS
                good_polys = []
                for poly in outlook.geometry:
                    intersect = CONUS["poly"].intersection(poly)
                    if isinstance(intersect, GeometryCollection):
                        for p in intersect:
                            if isinstance(p, Polygon):
                                good_polys.append(p)
                            else:
                                LOG.info("Discarding %s as not polygon", p)
                    else:
                        if isinstance(intersect, Polygon):
                            good_polys.append(intersect)
                        else:
                            LOG.info("Discarding %s as not polygon", intersect)
                outlook.geometry = MultiPolygon(good_polys)

                good_polys = []
                for poly1, poly2 in itertools.permutations(
                    outlook.geometry, 2
                ):
                    if poly1.contains(poly2):
                        rewrite = True
                        msg = (
                            "Discarding overlapping exterior polygon: "
                            "Day: %s %s %s Area: %.2f"
                        ) % (
                            day,
                            outlook.category,
                            outlook.threshold,
                            poly1.area,
                        )
                        LOG.info(msg)
                        self.warnings.append(msg)
                    elif tstm is not None and poly1.area > tstm.geometry.area:
                        rewrite = True
                        msg = (
                            "Discarding polygon as it is larger than TSTM: "
                            "Day: %s %s %s Area: %.2f"
                        ) % (
                            day,
                            outlook.category,
                            outlook.threshold,
                            poly1.area,
                        )
                        LOG.info(msg)
                        self.warnings.append(msg)
                    else:
                        if poly1 not in good_polys:
                            good_polys.append(poly1)
                if rewrite:
                    outlook.geometry = MultiPolygon(good_polys)

    def get_outlookcollection(self, day):
        """Returns the SPCOutlookCollection for a given day"""
        return self.outlook_collections.get(day)

    def get_outlook(self, category, threshold, day):
        """Get an outlook by category and threshold"""
        if day not in self.outlook_collections:
            return None
        for outlook in self.outlook_collections[day].outlooks:
            if outlook.category == category and outlook.threshold == threshold:
                return outlook
        return None

    def draw_outlooks(self):
        """For debugging, draw the outlooks on a simple map for inspection!"""
        from descartes.patch import PolygonPatch
        import matplotlib.pyplot as plt

        for day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
                fig = plt.figure(figsize=(12, 8))
                ax = fig.add_subplot(111)
                # pylint: disable=unsubscriptable-object
                ax.plot(
                    CONUS["line"][:, 0],
                    CONUS["line"][:, 1],
                    color="b",
                    label="Conus",
                )
                for poly in outlook.geometry:
                    patch = PolygonPatch(
                        poly,
                        fc="tan",
                        label="Outlook %.1f" % (poly.area,),
                        zorder=2,
                    )
                    ax.add_patch(patch)
                    ax.plot(
                        poly.exterior.xy[0],
                        poly.exterior.xy[1],
                        lw=2,
                        color="r",
                    )
                ax.set_title(
                    ("Day %s Category %s Threshold %s")
                    % (day, outlook.category, outlook.threshold)
                )
                ax.legend(loc=3)
                fn = (
                    ("/tmp/%s_%s_%s_%s.png")
                    % (
                        day,
                        self.issue.strftime("%Y%m%d%H%M"),
                        outlook.category,
                        outlook.threshold,
                    )
                ).replace(" ", "_")
                LOG.info(":: creating plot %s", fn)
                fig.savefig(fn)
                plt.close()

    def set_metadata(self):
        """
        Set some metadata about this product
        """
        if self.afos in ["PTSDY1", "PTSDY2", "PTSDY3", "PTSD48"]:
            self.outlook_type = "C"
        elif self.afos in ["PFWFD1", "PFWFD2", "PFWF38"]:
            self.outlook_type = "F"
        else:
            raise ValueError(f"Unknown awipsid '{self.afos}' for metadata")

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
        """Find the outlook sections within the text product!"""
        if self.text.find("&&") == -1:
            self.warnings.append("Product contains no &&, adding...")
            self.text = self.text.replace("\n... ", "\n&&\n... ")
            self.text += "\n&& "
        for segment in self.text.split("&&")[:-1]:
            day = get_day(self, segment)
            # We need to figure out the probabilistic or category
            tokens = re.findall(r"\.\.\.\s+(.*)\s+\.\.\.", segment)
            if not tokens:
                continue
            category = tokens[0].strip()
            point_data = {}
            # Now we loop over the lines looking for data
            threshold = None
            for line in segment.split("\n"):
                if (
                    re.match(
                        (
                            r"^(D[3-8]\-?[3-8]?|EXTM|MRGL|ENH|SLGT|MDT|ELEV|"
                            r"HIGH|CRIT|TSTM|SIGN|IDRT|SDRT|0\.[0-9][0-9]) "
                        ),
                        line,
                    )
                    is not None
                ):
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
                collect = self.get_outlookcollection(day)
            # We need to duplicate, in the case of day-day spans
            for threshold in list(point_data.keys()):
                if threshold == "TSTM" and self.afos == "PFWF38":
                    LOG.info(("Failing to parse TSTM in PFWF38"))
                    del point_data[threshold]
                    continue
                match = DMATCH.match(threshold)
                if match:
                    data = match.groupdict()
                    if data.get("day2") is not None:
                        day1 = int(data["day1"])
                        day2 = int(data["day2"])
                        LOG.info("Duplicating threshold %s-%s", day1, day2)
                        for i in range(day1, day2 + 1):
                            key = "D%s" % (i,)
                            point_data[key] = point_data[threshold]
                        del point_data[threshold]
            for threshold in point_data:
                match = DMATCH.match(threshold)
                if match:
                    day = int(match.groupdict()["day1"])
                    collect = self.get_outlookcollection(day)
                LOG.info(
                    "--> Start Day: %s Category: '%s' Threshold: '%s' =====",
                    day,
                    category,
                    threshold,
                )
                mp = str2multipolygon(point_data[threshold])
                if DMATCH.match(threshold):
                    threshold = "0.15"
                LOG.info("----> End threshold is: %s", threshold)
                collect.outlooks.append(SPCOutlook(category, threshold, mp))

    def compute_wfos(self, _txn=None):
        """Figure out which WFOs are impacted by this polygon"""
        # self.draw_outlooks()
        geodf = load_geodf("cwa")
        for day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
                if outlook.geometry.is_empty:
                    continue
                df2 = geodf[geodf["geom"].intersects(outlook.geometry)]
                outlook.wfos = df2.index.to_list()
                LOG.info(
                    "Day: %s Category: %s Threshold: %s #WFOS: %s %s",
                    day,
                    outlook.category,
                    outlook.threshold,
                    len(outlook.wfos),
                    ",".join(outlook.wfos),
                )

    def sql(self, txn):
        """Do database work

        Args:
          txn (psycopg2.cursor): database cursor
        """
        for day, collect in self.outlook_collections.items():
            _sql_day_collect(self, txn, day, collect)

    def get_descript_and_url(self):
        """Helper to convert awips id into strings"""
        product_descript = "((%s))" % (self.afos,)
        url = "https://www.spc.noaa.gov"
        day = "((%s))" % (self.afos,)

        if self.afos == "PTSDY1":
            day = "Day 1"
            product_descript = "Convective"
            url = (
                "https://www.spc.noaa.gov/products/outlook/archive/"
                "%s/day1otlk_%s.html"
            ) % (self.valid.year, self.issue.strftime("%Y%m%d_%H%M"))
        elif self.afos == "PTSDY2":
            day = "Day 2"
            product_descript = "Convective"
            hhmm = "1730" if self.valid.hour > 11 else "0600"
            url = (
                "https://www.spc.noaa.gov/products/outlook/archive/"
                "%s/day2otlk_%s_%s.html"
            ) % (self.valid.year, self.valid.strftime("%Y%m%d"), hhmm)
        elif self.afos == "PTSDY3":
            # 0730 when in CDT, 0830 when in CST
            hhmm = "0730" if self.z == "CDT" else "0830"
            day = "Day 3"
            product_descript = "Convective"
            url = (
                "https://www.spc.noaa.gov/products/outlook/archive/%s/"
                "day3otlk_%s_%s.html"
            ) % (self.valid.year, self.valid.strftime("%Y%m%d"), hhmm)
        elif self.afos == "PTSD48":
            day = "Days 4-8"
            product_descript = "Convective"
            url = (
                "https://www.spc.noaa.gov/products/exper/day4-8/archive/%s/"
                "day4-8_%s.html"
            ) % (self.valid.year, self.valid.strftime("%Y%m%d"))
        elif self.afos == "PFWFD1":
            day = "Day 1"
            product_descript = "Fire Weather"
            url = self.issue.strftime(
                (
                    "https://www.spc.noaa.gov/products/fire_wx/%Y/%y%m%d_%H%M"
                    "_fwdy1_print.html"
                )
            )
        elif self.afos == "PFWFD2":
            day = "Day 2"
            product_descript = "Fire Weather"
            url = self.issue.strftime(
                (
                    "https://www.spc.noaa.gov/products/fire_wx/%Y/%y%m%d_%H%M"
                    "_fwdy2_print.html"
                )
            )
        elif self.afos == "PFWF38":
            day = "Day 3-8"
            product_descript = "Fire Weather"
            url = self.issue.strftime(
                (
                    "https://www.spc.noaa.gov/products/exper/fire_wx/%Y/%y%m%d"
                    ".html"
                )
            )

        return product_descript, url, day

    def get_jabbers(self, uri, _uri2=None):
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
            "title": title,
            "name": "The Storm Prediction Center",
            "tstamp": self.valid.strftime("%b %-d, %-H:%Mz"),
            "outlooktype": product_descript,
            "url": url,
            "wfo": "DMX",  # autoplot expects something valid here
            "cat": self.outlook_type,
            "t220": "cwa",
        }
        twmedia = (
            "https://mesonet.agron.iastate.edu/plotting/auto/plot/220/"
            "cat:categorical::which:%(day)s%(cat)s::t:%(t220)s::network:WFO::"
            "wfo:%(wfo)s::"
            f"csector:conus::valid:{self.valid.strftime('%Y-%m-%d %H%M')}"
            ".png"
        ).replace(" ", "%%20")
        for day, collect in self.outlook_collections.items():

            wfos = {
                "TSTM": [],
                "EXTM": [],
                "MRGL": [],
                "SLGT": [],
                "ENH": [],
                "CRIT": [],
                "MDT": [],
                "HIGH": [],
                "ELEV": [],
                "IDRT": [],
                "SDRT": [],
            }

            for outlook in collect.outlooks:
                _d = wfos.setdefault(outlook.threshold, [])
                _d.extend(outlook.wfos)

            jdict["day"] = day
            wfomsgs = {}
            # We order in least to greatest, so that the highest threshold
            # overwrites lower ones
            for cat in [
                "MRGL",
                "SLGT",
                "ENH",
                "MDT",
                "HIGH",
                "ELEV",
                "CRIT",
                "EXTM",
                "IDRT",
                "SDRT",
            ]:
                jdict["ttext"] = "%s %s Risk" % (
                    THRESHOLD2TEXT[cat],
                    product_descript,
                )
                for wfo in wfos[cat]:
                    jdict["wfo"] = wfo
                    wfomsgs[wfo] = [
                        (
                            "%(name)s issues Day %(day)s %(ttext)s "
                            "at %(tstamp)s for portions of %(wfo)s %(url)s"
                        )
                        % jdict,
                        (
                            "<p>%(name)s issues "
                            '<a href="%(url)s">Day %(day)s %(ttext)s</a> '
                            "at %(tstamp)s for portions of %(wfo)s's area</p>"
                        )
                        % jdict,
                        {
                            "channels": [
                                wfo,
                                "%s.SPC%s" % (wfo, self.afos[3:]),
                                "%s.SPC%s.%s" % (wfo, self.afos[3:], cat),
                            ],
                            "product_id": self.get_product_id(),
                            "twitter_media": twmedia % jdict,
                            "twitter": (
                                "SPC issues Day %(day)s %(ttext)s "
                                "at %(tstamp)s for %(wfo)s %(url)s"
                            )
                            % jdict,
                        },
                    ]
            keys = list(wfomsgs.keys())
            keys.sort()
            res = []
            for wfo in keys:
                res.append(wfomsgs[wfo])

        # Generic for SPC
        jdict["t220"] = "conus"
        if len(self.outlook_collections) > 1:
            jdict["day"] = "0"
        res.append(
            [
                (
                    "%(name)s issues %(title)s %(outlooktype)s Outlook at "
                    "%(tstamp)s %(url)s"
                )
                % jdict,
                (
                    '<p>%(name)s issues <a href="%(url)s">%(title)s '
                    "%(outlooktype)s Outlook</a> at %(tstamp)s</p>"
                )
                % jdict,
                {
                    "channels": ["SPC", "SPC%s" % (self.afos[3:],)],
                    "product_id": self.get_product_id(),
                    "twitter_media": twmedia % jdict,
                    "twitter": (
                        "%(name)s issues %(title)s "
                        "%(outlooktype)s Outlook at %(tstamp)s %(url)s"
                    )
                    % jdict,
                },
            ]
        )
        return res


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Parse this text!"""
    return SPCPTS(text, utcnow, ugc_provider, nwsli_provider)
