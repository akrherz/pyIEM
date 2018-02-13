"""Test our caching zonal_stats"""
import unittest

import numpy as np
from geopandas import GeoSeries
from shapely.geometry import Polygon
from affine import Affine
from pyiem.grid import zs


class CachingZonalStatstest(unittest.TestCase):
    """Test all things"""

    def test_gen_stats(self):
        """Run a test"""
        affine = Affine(10., 0., 0., 0., -10, 100)
        grid = np.reshape(np.arange(100), (10, 10))
        sq1 = Polygon([(50, 50), (50, 60), (60, 60), (60, 50)])
        sq2 = Polygon([(60, 60), (60, 70), (70, 70), (70, 60)])
        geometries = GeoSeries([sq1, sq2])
        czs = zs.CachingZonalStats(affine)
        res = czs.gen_stats(np.flipud(grid), geometries)
        self.assertEquals(len(res), 2)
        self.assertAlmostEqual(res[0], 55.0, 1)
        self.assertAlmostEqual(res[1], 66.0, 1)

        czs = zs.CachingZonalStats(affine)
        res = czs.gen_stats(np.flipud(grid))
        self.assertTrue(not res)
