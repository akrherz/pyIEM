"""tests"""

import pytest
from shapely.geometry import Point, Polygon, LineString
from pyiem import wellknowntext


def test_parsecoordinate_lists():
    """Parse!"""
    with pytest.raises(ValueError):
        wellknowntext.parse_coordinate_lists("  ")


def test_unknown():
    """Test an emptry string."""
    with pytest.raises(ValueError):
        wellknowntext.convert_well_known_text("")


def test_wkt():
    """Try the properties function"""
    wkt = "SRID=4326;POINT(-99 43)"
    geom = wellknowntext.convert_well_known_text(wkt)
    assert Point(geom) == Point([-99, 43])

    wkt = """MULTIPOLYGON (((40 40, 20 45, 45 30, 40 40)),
        ((20 35, 10 30, 10 10, 30 5, 45 20, 20 35),
        (30 20, 20 15, 20 25, 30 20)))"""
    geom = wellknowntext.convert_well_known_text(wkt)
    assert abs(Polygon(geom[0]).area - 87.5) < 0.1

    wkt = """MULTILINESTRING ((10 10, 20 20, 10 40),
    (40 40, 30 30, 40 20, 30 10))"""
    geom = wellknowntext.convert_well_known_text(wkt)
    assert abs(LineString(geom[0]).length - 36.5) < 0.1

    wkt = """LINESTRING (30 10, 10 30, 40 40)"""
    geom = wellknowntext.convert_well_known_text(wkt)
    assert abs(LineString(geom).length - 59.9) < 0.1

    wkt = """POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))"""
    geom = wellknowntext.convert_well_known_text(wkt)
    assert abs(Polygon(geom[0]).area - 550.0) < 0.1

    wkt = """POLYGON q((30 10, 40 40, 20 40, 10 20, 30 10))q"""
    with pytest.raises(ValueError):
        wellknowntext.convert_well_known_text(wkt)

    wkt = """RARRR q((30 10, 40 40, 20 40, 10 20, 30 10))q"""
    with pytest.raises(ValueError):
        wellknowntext.convert_well_known_text(wkt)

    with pytest.raises(ValueError):
        wellknowntext.convert_well_known_text("")
