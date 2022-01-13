"""Geometry utility functions."""

# third party
from shapely.geometry import (
    MultiPolygon,
    Point,
    MultiLineString,
    GeometryCollection,
)
from shapely.ops import split

# Local
from pyiem.util import LOG


def rhs_split(poly, splitter):
    """Provide the Right Hand Side Polygon associated with a split operation.

    Args:
      poly (shapely.geometry.Polygon): polygon to split.
      splitter (shapely.geometry.LineString): linestring to spliy by.

    Returns:
      shapely.geometry.Polygon
    """
    # compute the part of the splitter that intersects the polygon
    split_intersection = splitter.intersection(poly)
    # May be a MultiLineString
    if isinstance(split_intersection, (MultiLineString, GeometryCollection)):
        # Just take the first one, it should not matter as long as it is
        # not a Point object
        if isinstance(split_intersection.geoms[0], Point):
            split_intersection = split_intersection.geoms[1]
        else:
            split_intersection = split_intersection.geoms[0]

    # do the splitting
    geomcollect = split(poly, splitter)
    # If we got more than two polygons, we likely can cull some small cruft
    if len(geomcollect.geoms) > 2:
        geomcollect = MultiPolygon(
            [geo for geo in geomcollect.geoms if geo.area > 0.1]
        )
        if len(geomcollect.geoms) > 2:
            LOG.warning("intersection found more than 2 polys, failing")
            return None
    if len(geomcollect.geoms) == 1:
        return geomcollect.geoms[0]
    (polya, polyb) = geomcollect.geoms[0], geomcollect.geoms[1]
    # We project two points along the splitter intersection back onto polya
    pt0 = Point(split_intersection.coords[0])
    pt1 = Point(split_intersection.coords[1])
    start_dist = polya.exterior.project(pt0)
    end_dist = polya.exterior.project(pt1)
    return polya if end_dist > start_dist else polyb
