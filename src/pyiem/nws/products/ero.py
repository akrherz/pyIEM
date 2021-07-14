"""
Eh, I am able to parse the SPC PTS now, so why not add more pain.

Weather Prediction Center Excessive Rainfall Outlook.
"""
import re
import datetime
import os
import tempfile
import math

import numpy as np
import pandas as pd
from shapely.geometry import (
    Polygon,
    LineString,
    MultiPolygon,
    Point,
)
from shapely.geometry.polygon import LinearRing
from shapely.affinity import translate
from metpy.units import units

# Local
from pyiem.reference import txt2drct
from pyiem.geom_util import rhs_split
from pyiem.nws.product import TextProduct
from pyiem.util import LOG, load_geodf

CONUS = {"line": None, "poly": None}
RISK_RE = re.compile(
    r"^(?P<cat>MARGINAL|SLIGHT|MODERATE|HIGH)",
    re.I,
)
VALID_RE = re.compile(
    r"Valid\s+(?P<start>[0-9]{1,4})Z?\s+...\s+(?P<smonth>[A-Z]{3})\s+"
    r"(?P<sday>\d+)\s+(?P<syear>\d\d\d\d)\s+\-\s+"
    r"(?P<end>[0-9]{1,4})Z?\s+...\s+(?P<emonth>[A-Z]{3})\s+"
    r"(?P<eday>\d+)\s+(?P<eyear>\d\d\d\d)",
    re.IGNORECASE,
)

TEXT2THRESHOLD = {
    "MARGINAL": "MRGL",
    "SLIGHT": "SLGT",
    "ENHANCED": "ENH",
    "MODERATE": "MDT",
    "HIGH": "HIGHT",
}
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
THRESHOLD_ORDER = (
    "0.02 0.05 0.10 0.15 0.25 0.30 0.35 0.40 0.45 0.60 TSTM MRGL SLGT ENH"
    "MDT HIGH IDRT SDRT ELEV CRIT EXTM"
).split()


def load_conus_data():
    """Load up the conus datafile for our perusal"""
    fn = "%s/../../data/conus_marine_bnds.txt" % (os.path.dirname(__file__),)
    lons = []
    lats = []
    with open(fn) as fh:
        for line in fh:
            tokens = line.split(",")
            lons.append(float(tokens[0]))
            lats.append(float(tokens[1]))
    CONUS["line"] = np.column_stack([lons, lats])
    CONUS["poly"] = Polygon(CONUS["line"])


def point_outside_conus(pt):
    """Is this point safely outside the CONUS bounds."""
    return not pt.within(CONUS["poly"]) and pt.distance(CONUS["poly"]) > 0.001


def get_conus_point(pt):
    """Return interpolated point from projection to CONUS."""
    return CONUS["poly"].exterior.interpolate(
        CONUS["poly"].exterior.project(pt)
    )


def ensure_outside_conus(ls):
    """Make sure the start and end of a given line are outside the CONUS."""
    # First and last point of the ls need to be exterior to the CONUS
    for idx in [0, -1]:
        pt = Point(ls.coords[idx])
        # If point is safely outside CONUS, done.
        if point_outside_conus(pt):
            continue
        # Get new point that may be too close for comfort
        pt = get_conus_point(pt)
        if pt.within(CONUS["poly"]) or pt.distance(CONUS["poly"]) < 0.001:
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


def condition_segment(segment):
    """Do conditioning of the segment."""
    # 1. If the start and end points are the same, done and one
    if segment[0][0] == segment[-1][0] and segment[0][1] == segment[-1][1]:
        if len(segment) == 2:
            LOG.info("    REJECTING two point segment, both equal")
            return None
        return [segment]
    # 2. If point start and end points are inside the conus and they are closer
    #    to each other than the CONUS bounds, then close off polygon
    if all(not point_outside_conus(Point(segment[i])) for i in [0, -1]):
        pt0 = Point(segment[0])
        pt1 = Point(segment[-1])
        cpt0 = get_conus_point(pt0)
        cpt1 = get_conus_point(pt1)
        cdist0 = cpt0.distance(pt0)
        cdist1 = cpt1.distance(pt1)
        if pt0.distance(pt1) < 0.5 * min([cdist0, cdist1]):
            LOG.info("     non-closed polygon assumed unclosed in error.")
            segment.append(segment[0])
            return [segment]
    # 3. If the line intersects the CONUS 3+ times, split the line
    ls = ensure_outside_conus(LineString(segment))
    # Examine how our linestring intersects the CONUS polygon
    res = ls.intersection(CONUS["poly"])
    if isinstance(res, LineString):
        return [ls.coords]
    # We got multiple linestrings
    res = [r for r in res if r.length > 0.2]  # pylint: disable=not-an-iterable
    if len(res) == 1:
        LOG.info("    was able to filter out very short lines")
        return [ensure_outside_conus(res[0]).coords]
    LOG.info("     returning a MultiLineString len=%s", len(res))
    return [ensure_outside_conus(x).coords for x in res]


def convert_segments(segments):
    """Figure out what we have here for segments."""
    polygons = []
    interiors = []
    linestrings = []
    for segment in segments:
        ls = LineString(segment)
        if segment[0][0] == segment[-1][0] and segment[0][1] == segment[-1][1]:
            lr = LinearRing(ls)
            if not lr.is_ccw:
                polygons.append(Polygon(segment))
            else:
                interiors.append(lr)
            continue
        linestrings.append(ls)

    return polygons, interiors, linestrings


def compute_start_end_points(linestrings):
    """Figure out where each line string starts."""
    starts = []
    stops = []
    for ls in linestrings:
        pt = Point(ls.coords[0])
        starts.append(round(CONUS["poly"].exterior.project(pt), 2))
        pt = Point(ls.coords[-1])
        stops.append(round(CONUS["poly"].exterior.project(pt), 2))
    return starts, stops


def winding_logic(linestrings):
    """Make polygons from our linestrings!"""
    # Winding Rule: project the starting point of the linestrings onto the
    # CONUS linear ring.
    start_dists, end_dists = compute_start_end_points(linestrings)
    df = pd.DataFrame({"start": start_dists, "end": end_dists})
    df = df.sort_values("start", ascending=True).reindex()
    df["used"] = False
    polys = []
    for i in df.index:
        # Check if we have used this line already or not
        if df.at[i, "used"]:
            LOG.debug("     skipping %s as already used.", i)
            continue
        df.at[i, "used"] = True
        started_at = df.at[i, "start"]
        LOG.debug("   looping %s, started_at %s", i, started_at)
        poly = rhs_split(CONUS["poly"], linestrings[i])
        ended_at = df.at[i, "end"]
        for _q in range(100):  # belt-suspenders to keep infinite loop
            LOG.debug("     looping with ended_at of %s", ended_at)
            # Look for the next line that starts before we get back around
            if ended_at < started_at:
                df2 = df[
                    ~df["used"]
                    & ((df["start"] >= ended_at) & (df["start"] < started_at))
                ]
            else:
                df2 = df[
                    ~df["used"]
                    & ((df["start"] >= ended_at) | (df["start"] < started_at))
                ]
            LOG.debug("     found %s filtered rows", len(df2.index))
            if df2.empty:
                LOG.info("     i=%s adding poly: %.3f", i, poly.area)
                if poly not in polys:
                    polys.append(poly)
                else:
                    LOG.info("     this polygon is a dup, skipping")
                break
            # updated ended_at
            ended_at = df2.iloc[0]["end"]
            df.at[df2.index[0], "used"] = True
            poly = rhs_split(poly, linestrings[df2.index[0]])
    return polys


def init_days(prod):
    """Figure out which days this product should have based on the AFOS."""
    day = 1
    if prod.afos == "PBG98E":
        day = 2
    elif prod.afos == "PBG99E":
        day = 3
    return day, {day: OutlookCollection(prod.issue, prod.expire, day)}


def _compute_cycle(prod):
    """Figure out an integer cycle that identifies this product."""
    if prod.day == 1:
        if prod.valid.hour in range(0, 6):
            return 1
        if prod.valid.hour in range(6, 13):
            return 8
        if prod.valid.hour in range(13, 20):
            return 16
    if prod.valid.hour in range(4, 12):
        return 8
    if prod.valid.hour in range(17, 22):
        return 20
    return -1


def _sql_set_cycle(txn, outlook_id, cycle):
    """Assign a given outlook a given cycle."""
    txn.execute(
        "UPDATE spc_outlook SET cycle = %s, updated = now() where id = %s",
        (cycle, outlook_id),
    )


def _sql_cycle_canonical(prod, txn, day, collect, outlook_id):
    """Check our database."""
    txn.execute(
        "SELECT id, product_issue from spc_outlook where expire = %s and "
        "outlook_type = %s and day = %s and cycle = %s",
        (collect.expire, prod.outlook_type, day, prod.cycle),
    )
    if txn.rowcount == 0:  # yes
        LOG.info("Setting as canonical cycle of %s", prod.cycle)
        _sql_set_cycle(txn, outlook_id, prod.cycle)
    else:
        # tricky
        is_canonical = True
        for row in txn.fetchall():
            if row["product_issue"] < prod.valid:
                LOG.info(
                    "Setting old outlook %s to cycle=-1, product_issue = %s "
                    ", prod.valid = %s",
                    row["id"],
                    row["product_issue"],
                    prod.valid,
                )
                _sql_set_cycle(txn, row["id"], -1)
            elif row["product_issue"] > prod.valid:
                is_canonical = False
        cycle = prod.cycle if is_canonical else -1
        LOG.info("Setting this outlook to cycle=%s", cycle)
        _sql_set_cycle(txn, outlook_id, cycle)


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
        # Update the updated column
        txn.execute(
            "UPDATE spc_outlook SET updated = now() WHERE id = %s",
            (outlook_id,),
        )
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


def compute_loc(lon, lat, dist, bearing):
    """Estimate a lat/lon"""
    meters = (units("mile") * dist).to(units("meter")).m
    northing = meters * math.cos(math.radians(bearing)) / 111111.0
    easting = (
        meters
        * math.sin(math.radians(bearing))
        / math.cos(math.radians(lat))
        / 111111.0
    )
    return lon + easting, lat + northing


def meat2segment(meat):
    """Convert into a list of points."""
    asos = load_geodf("asos")
    tokens = meat.split()
    sz = len(tokens)
    i = 0
    pts = []
    while i < sz:
        token = tokens[i]
        if token.isdigit() and (i + 2) < sz:
            miles = float(token)
            drct = txt2drct.get(tokens[i + 1])
            sid = tokens[i + 2]
            row = asos.loc[sid]
            pts.append(compute_loc(row["geom"].x, row["geom"].y, miles, drct))
            i += 3
            continue
        sid = tokens[i]
        row = asos.loc[sid]
        pts.append([row["geom"].x, row["geom"].y])
        i += 1
    return pts


class OutlookCollection:
    """A collection of outlooks for a single 'day'"""

    def __init__(self, issue, expire, day):
        """Constructor"""
        self.issue = issue
        self.expire = expire
        self.day = day
        self.outlooks = []


class Outlook:
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


class ERO(TextProduct):
    """A class representing the polygons and metadata in WPC ERO Product"""

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
        LOG.info("==== ERO Processing: %s", self.get_product_id())
        load_conus_data()
        self.issue = None
        self.expire = None
        self.outlook_type = "E"
        self.find_issue_expire()
        self.day, self.outlook_collections = init_days(self)
        self.find_outlooks()
        self.quality_control()
        self.compute_wfos()
        self.cycle = _compute_cycle(self)

    def quality_control(self):
        """Run some checks against what was parsed"""
        # 1. Do polygons overlap for the same outlook
        LOG.info("==== Running Quality Control Checks")
        for _day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
                good_polys = []
                for poly in outlook.geometry:
                    if poly.area < 0.1:
                        msg = (
                            f"Impossibly small polygon.area {poly.area:.2f} "
                            "discarded"
                        )
                        LOG.info(msg)
                        self.warnings.append(msg)
                        continue
                    intersect = CONUS["poly"].intersection(poly)
                    # Current belief is that we can only return a (multi)poly
                    if isinstance(intersect, MultiPolygon):
                        for p in intersect:
                            good_polys.append(p)
                    elif isinstance(intersect, Polygon):
                        good_polys.append(intersect)
                outlook.geometry = MultiPolygon(good_polys)

                # All geometries in the outlook shall not overlap with any
                # other one, if so, cull it!
                good_polys = []
                for i, poly in enumerate(outlook.geometry):
                    passes_check = True
                    for i2, poly2 in enumerate(outlook.geometry):
                        if i == i2:
                            continue
                        if not poly.intersects(poly2):
                            continue
                        passes_check = False
                        msg = (
                            f"Discarding polygon idx: {i} as it intersects "
                            f"idx: {i2} Area: {poly.area:.2f}"
                        )
                        LOG.info(msg)
                        self.warnings.append(msg)
                        break
                    if passes_check:
                        good_polys.append(poly)
                outlook.geometry = MultiPolygon(good_polys)

    def get_outlookcollection(self, day):
        """Returns the OutlookCollection for a given day"""
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
        # pylint: disable=import-outside-toplevel
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
                    ("%s/%s_%s_%s_%s.png")
                    % (
                        tempfile.gettempdir(),
                        day,
                        self.issue.strftime("%Y%m%d%H%M"),
                        outlook.category,
                        outlook.threshold,
                    )
                ).replace(" ", "_")
                LOG.info(":: creating plot %s", fn)
                fig.savefig(fn)
                plt.close()

    def find_issue_expire(self):
        """
        Determine the period this product is valid for
        """
        m = VALID_RE.findall(self.text)[0]
        if len(m[0]) >= 3:
            hour1 = int(m[0][:2])
            minute1 = int(m[0][-2:])
        else:
            hour1 = int(m[0])
            minute1 = 0
        if len(m[4]) >= 3:
            hour2 = int(m[4][:2])
            minute2 = int(m[4][-2:])
        else:
            hour2 = int(m[4])
            minute2 = 0
        sts = "%s:%s %s %s %s" % (
            hour1,
            minute1,
            m[1],
            m[2],
            m[3],
        )
        sts = datetime.datetime.strptime(sts, "%H:%M %b %d %Y")
        sts = sts.replace(tzinfo=datetime.timezone.utc)
        ets = "%s:%s %s %s %s" % (
            hour2,
            minute2,
            m[5],
            m[6],
            m[7],
        )
        ets = datetime.datetime.strptime(ets, "%H:%M %b %d %Y")
        ets = ets.replace(tzinfo=datetime.timezone.utc)
        self.issue = sts
        self.expire = ets

    def find_outlooks(self):
        """Find the outlook sections within the text product!"""
        text = "\n".join([x.strip() for x in self.text.split("\n")])
        tokens = text.strip().split("\n\n")
        point_data = {}
        for token in tokens:
            section = token.strip().replace("\n", " ")
            m = RISK_RE.match(section)
            if m is None:
                continue
            threshold = TEXT2THRESHOLD[m.groupdict()["cat"]]
            arr = point_data.setdefault(threshold, [])
            meat = section.split(" FROM ", 1)[1].replace(".", "")
            arr.append(meat2segment(meat))
        collect = self.get_outlookcollection(self.day)
        for threshold, pdata in point_data.items():
            segments = []
            for segment in pdata:
                res = condition_segment(segment)
                if res:
                    segments.extend(res)
            polygons, _interiors, linestrings = convert_segments(segments)
            # we do our winding logic now
            polygons.extend(winding_logic(linestrings))
            mp = MultiPolygon(polygons)
            collect.outlooks.append(Outlook("CATEGORICAL", threshold, mp))

    def compute_wfos(self, _txn=None):
        """Figure out which WFOs are impacted by this polygon"""
        # self.draw_outlooks()
        geodf = load_geodf("cwa")
        for day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
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

    def get_jabbers(self, uri, _uri2=None):
        """Wordsmith the Jabber/Twitter Messaging"""
        res = []
        url = "https://www.wpc.ncep.noaa.gov/archives/web_pages/ero/ero.shtml"
        product_descript = "Excessive Rainfall Outlook"
        jdict = {
            "title": product_descript,
            "name": "The Weather Prediction Center",
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
                "MRGL": [],
                "SLGT": [],
                "ENH": [],
                "MDT": [],
                "HIGH": [],
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
                                "%s.ERO%s" % (wfo, self.afos[3:]),
                                "%s.ERO%s.%s" % (wfo, self.afos[3:], cat),
                            ],
                            "product_id": self.get_product_id(),
                            "twitter_media": twmedia % jdict,
                            "twitter": (
                                "WPC issues Day %(day)s %(ttext)s "
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

        # Generic for WPC
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
                    "channels": ["WNH", "ERO%s" % (self.afos[3:],)],
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
    return ERO(text, utcnow, ugc_provider, nwsli_provider)
