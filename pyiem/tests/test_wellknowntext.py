import unittest
from shapely.geometry import Point, Polygon, LineString
from pyiem import wellknowntext


class TestWKT(unittest.TestCase):

    def test_wkt(self):
        """ Try the properties function"""
        wkt = "SRID=4326;POINT(-99 43)"
        geom = wellknowntext.convert_well_known_text(wkt)
        self.assertEquals(Point(geom), Point([-99, 43]))

        wkt = """MULTIPOLYGON (((40 40, 20 45, 45 30, 40 40)),
            ((20 35, 10 30, 10 10, 30 5, 45 20, 20 35),
            (30 20, 20 15, 20 25, 30 20)))"""
        geom = wellknowntext.convert_well_known_text(wkt)
        self.assertAlmostEquals(Polygon(geom[0]).area, 87.5, 1)

        wkt = """MULTILINESTRING ((10 10, 20 20, 10 40),
        (40 40, 30 30, 40 20, 30 10))"""
        geom = wellknowntext.convert_well_known_text(wkt)
        self.assertAlmostEquals(LineString(geom[0]).length, 36.5, 1)

        wkt = """LINESTRING (30 10, 10 30, 40 40)"""
        geom = wellknowntext.convert_well_known_text(wkt)
        self.assertAlmostEquals(LineString(geom).length, 59.9, 1)

        wkt = """POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))"""
        geom = wellknowntext.convert_well_known_text(wkt)
        self.assertAlmostEquals(Polygon(geom[0]).area, 550., 1)

        wkt = """POLYGON q((30 10, 40 40, 20 40, 10 20, 30 10))q"""
        self.assertRaises(ValueError,
                          wellknowntext.convert_well_known_text, wkt)

        wkt = """RARRR q((30 10, 40 40, 20 40, 10 20, 30 10))q"""
        self.assertRaises(ValueError,
                          wellknowntext.convert_well_known_text, wkt)

        self.assertRaises(ValueError,
                          wellknowntext.convert_well_known_text, '')
