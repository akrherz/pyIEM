"""Shared code between SPC PTS and WPC ERO parsers."""
# stdlib
import os
import tempfile

# Third Party
import numpy as np
import pandas as pd
from shapely.affinity import translate
from shapely.geometry.polygon import LinearRing
from shapely.geometry import Polygon, Point, LineString

# local
from pyiem.geom_util import rhs_split
from pyiem.util import utc, LOG

CONUS_BASETIME = utc(2019, 5, 9, 16)
CONUS = {"line": None, "poly": None}
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


def load_conus_data(valid=None):
    """Load up the conus datafile for our perusal"""
    valid = utc() if valid is None else valid
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


def debug_draw(i, segment):
    """Draw this for debugging purposes."""
    segment = np.array(segment)
    # pylint: disable=import-outside-toplevel
    from pyiem.plot.use_agg import plt

    (fig, ax) = plt.subplots(1, 1)
    ax.plot(segment[:, 0], segment[:, 1], c="b")
    ax.plot(CONUS["poly"].exterior.xy[0], CONUS["poly"].exterior.xy[1], c="r")
    mydir = tempfile.gettempdir()
    LOG.info("writting %s/%sdebugdraw.png", mydir, i)
    fig.savefig(f"{mydir}/{i}debugdraw.png")
    return fig


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
