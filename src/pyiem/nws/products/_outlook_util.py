"""Shared code between SPC PTS and WPC ERO parsers."""

# stdlib
import os
import tempfile

# Third Party
import numpy as np
import pandas as pd
from shapely.affinity import translate
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.polygon import LinearRing

# local
from pyiem.geom_util import rhs_split
from pyiem.util import LOG, utc

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
    "0.15": "15% Any Severe",
    "0.30": "30% Any Severe",
}


def load_conus_data(valid=None):
    """Load up the conus datafile for our perusal"""
    valid = utc() if valid is None else valid
    fn = (
        f"{os.path.dirname(__file__)}/../../data/conus_marine_bnds"
        f"{'_pre190509' if valid < CONUS_BASETIME else ''}.txt"
    )
    lons = []
    lats = []
    with open(fn, encoding="utf-8") as fh:
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
            LOG.warning("     idx: %s is still within, evasive action", idx)
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
                        LOG.warning("     idx: %s is now %s", idx, pt)
                        done = True
                        break
        LOG.warning(
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
    from pyiem.plot.use_agg import figure

    fig = figure(figsize=(10, 10), dpi=100)
    ax = fig.add_subplot(111)
    ax.plot(segment[:, 0], segment[:, 1], c="b")
    ax.plot(CONUS["poly"].exterior.xy[0], CONUS["poly"].exterior.xy[1], c="r")
    mydir = tempfile.gettempdir()
    LOG.warning("writting %s/%sdebugdraw.png", mydir, i)
    fig.savefig(f"{mydir}/{i}debugdraw.png")
    return fig


def condition_segment(segment):
    """Do conditioning of the segment."""
    # 1. If the start and end points are the same, done and one
    if segment[0][0] == segment[-1][0] and segment[0][1] == segment[-1][1]:
        if len(segment) == 2:
            LOG.warning("    REJECTING two point segment, both equal")
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
            LOG.warning("     non-closed polygon assumed unclosed in error.")
            segment.append(segment[0])
            return [segment]
    # 3. If the line intersects the CONUS 3+ times, split the line
    ls = ensure_outside_conus(LineString(segment))
    # Examine how our linestring intersects the CONUS polygon
    res = ls.intersection(CONUS["poly"])
    if isinstance(res, LineString):
        return [ls.coords]
    # We got multiple linestrings
    # pylint: disable=no-member
    res = [r for r in res.geoms if r.length > 0.2]
    if len(res) == 1:
        LOG.warning("    was able to filter out very short lines")
        return [ensure_outside_conus(res[0]).coords]
    LOG.warning("     returning a MultiLineString len=%s", len(res))
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
        if poly is None:
            raise ValueError("rhs_split failed, aborting")
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
                LOG.warning("     i=%s adding poly: %.3f", i, poly.area)
                if poly not in polys:
                    polys.append(poly)
                else:
                    LOG.warning("     this polygon is a dup, skipping")
                break
            # updated ended_at
            ended_at = df2.iloc[0]["end"]
            df.at[df2.index[0], "used"] = True
            poly = rhs_split(poly, linestrings[df2.index[0]])
    return polys


def sql_day_collect(prod, txn, day, collect):
    """Do database work."""
    # Compute what our outlook identifier is
    txn.execute(
        "SELECT id from spc_outlook where product_issue = %s and "
        "day = %s and outlook_type = %s",
        (prod.valid, day, prod.outlook_type),
    )
    if txn.rowcount > 0:
        outlook_id = txn.fetchone()["id"]
        # Do some deleting
        txn.execute(
            "DELETE from spc_outlook_geometries where spc_outlook_id = %s",
            (outlook_id,),
        )
        LOG.warning(
            "Removed %s rows from spc_outlook_geometries", txn.rowcount
        )
        # Delete the old entry here as well
        txn.execute(
            "DELETE from spc_outlook WHERE id = %s",
            (outlook_id,),
        )
        LOG.warning("Removed %s rows from spc_outlook", txn.rowcount)
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
    outlook_id = txn.fetchone()["id"]
    # Now, are we the canonical outlook for this cycle?
    if prod.cycle > -1:
        _sql_cycle_canonical(prod, txn, day, collect, outlook_id)
    for outlook in collect.outlooks:
        if outlook.geometry.is_empty:
            prod.warnings.append(
                f"No Outlook.geometry {outlook.category} {outlook.threshold}"
            )
            continue
        txn.execute(
            """
            INSERT into spc_outlook_geometries(spc_outlook_id, threshold,
            category, geom, geom_layers) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                outlook_id,
                outlook.threshold,
                outlook.category,
                f"SRID=4326;{outlook.geometry.wkt}",
                f"SRID=4326;{outlook.geometry_layers.wkt}",
            ),
        )


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
        LOG.warning("Setting as canonical cycle of %s", prod.cycle)
        _sql_set_cycle(txn, outlook_id, prod.cycle)
    else:
        # tricky
        for row in txn.fetchall():
            if row["product_issue"] < prod.valid:
                LOG.warning(
                    "Setting old outlook %s to cycle=-1, product_issue = %s "
                    ", prod.valid = %s",
                    row["id"],
                    row["product_issue"],
                    prod.valid,
                )
                _sql_set_cycle(txn, row["id"], -1)
            elif row["product_issue"] > prod.valid:
                prod.cycle = -1
        LOG.warning("Setting this outlook to cycle=%s", prod.cycle)
        _sql_set_cycle(txn, outlook_id, prod.cycle)


def compute_layers(prod):
    """Compute the differenced geomtries."""
    # 1. Do polygons overlap for the same outlook
    LOG.warning("==== Running Geometry differences")
    for day in prod.outlook_collections:
        prod.outlook_collections[day].difference_geometries()


def quality_control(prod):
    """Do Quality Control work."""
    # 1. Do polygons overlap for the same outlook
    LOG.warning("==== Running Quality Control Checks")
    for day, collect in prod.outlook_collections.items():
        # Everything should be smaller than General Thunder, for conv
        tstm = prod.get_outlook("CATEGORICAL", "TSTM", day)
        for outlook in collect.outlooks[::-1]:
            good_polys = []
            for poly in outlook.geometry_layers.geoms:
                if tstm and poly.area > tstm.geometry_layers.area:
                    msg = (
                        "Discarding polygon as it is larger than TSTM: "
                        f"{outlook.category} {outlook.threshold} "
                        f"Area: {outlook.geometry_layers.area:.2f} "
                        f"TSTM Area: {tstm.geometry_layers.area:.2f}"
                    )
                    LOG.warning(msg)
                    prod.warnings.append(msg)
                    continue
                if poly.area < 0.1:
                    msg = (
                        f"Impossibly small polygon.area {poly.area:.2f} "
                        "discarded"
                    )
                    LOG.warning(msg)
                    continue
                intersect = CONUS["poly"].intersection(poly)
                # Current belief is that we can only return a (multi)poly
                if isinstance(intersect, MultiPolygon):
                    good_polys.extend(list(intersect.geoms))
                elif isinstance(intersect, Polygon):
                    good_polys.append(intersect)
            outlook.geometry_layers = MultiPolygon(good_polys)

            # All geometries in the outlook shall not overlap with any
            # other one, if so, cull it!
            good_polys = []
            for i, poly in enumerate(outlook.geometry_layers.geoms):
                passes_check = True
                for i2, poly2 in enumerate(outlook.geometry_layers.geoms):
                    if i == i2:
                        continue
                    intersection = poly.intersection(poly2)
                    if intersection.is_empty:
                        continue
                    if intersection.area < 0.1:
                        LOG.warning("Ignoring small intersection of polygons")
                        continue
                    passes_check = False
                    msg = (
                        f"Discarding polygon idx: {i} as it intersects "
                        f"idx: {i2} Area: {poly.area:.2f}"
                    )
                    LOG.warning(msg)
                    prod.warnings.append(msg)
                    break
                if passes_check:
                    good_polys.append(poly)
            outlook.geometry_layers = MultiPolygon(good_polys)
