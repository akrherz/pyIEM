"""Exercise pyiem.geom_util"""

# Third Party
from shapely.geometry import Polygon, LineString

# Local
from pyiem import geom_util

SQUARE = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])


def test_three_polygon_intersection():
    """Test what happens when we divide a polygon three times."""
    res = geom_util.rhs_split(
        SQUARE,
        LineString([(0.5, -0.1), (0.5, 1.1), (0.7, 1.1), (0.7, -0.1)]),
    )
    assert res is None


def test_coincident_splitter():
    """Test what happens when provided a splitter that is coincident."""
    res = geom_util.rhs_split(SQUARE, LineString([(0, 0), (1, 0)]))
    assert res.area == 1


def test_crossing_origin():
    """Test what we get the right polygon when crossing the origin."""
    res = geom_util.rhs_split(SQUARE, LineString([(1, 0.5), (0.5, 0)]))
    assert res.area == 0.875
