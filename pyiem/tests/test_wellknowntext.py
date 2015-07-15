import unittest
from shapely.geometry import Point
from pyiem import wellknowntext


class TestWKT(unittest.TestCase):

    def test_wkt(self):
        """ Try the properties function"""
        wkt = "SRID=4326;POINT(-99 43)"
        geom = wellknowntext.convert_well_known_text(wkt)
        self.assertEquals(Point(geom), Point([-99, 43]))
