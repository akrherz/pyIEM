"""tests"""
import unittest
import datetime

from pyiem import prism


class PRISMTests(unittest.TestCase):
    """our tests"""

    def test_ij(self):
        """Can we get valid indices back!"""
        res = prism.find_ij(-98.0, 32)
        self.assertEquals(res[0], 647)

        res = prism.find_ij(98.0, 32)
        self.assertTrue(res[0] is None)

    def test_tidx(self):
        """Can we get time indices"""
        valid = datetime.datetime(2017, 9, 1)
        tidx = prism.daily_offset(valid)
        self.assertEquals(tidx, 243)
