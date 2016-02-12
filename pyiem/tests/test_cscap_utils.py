from pyiem.cscap_utils import Worksheet, translate_years
import unittest


class Test(unittest.TestCase):

    def test_translateyears(self):
        """See that we can translate years properly"""
        x = translate_years("X ('07-'17)")
        self.assertEquals(x[0], 2007)
        x = translate_years("X ('98-'06)")
        self.assertEquals(x[0], 1998)
        self.assertEquals(x[-1], 2006)
        x = translate_years("X ('14, '15, '16, '17)")
        self.assertEquals(x[0], 2014)
        self.assertEquals(x[-1], 2017)
        x = translate_years("X ('06)")
        self.assertEquals(x[0], 2006)

    def test_worksheet(self):
        """Worksheet"""
        w = Worksheet(None, None)
        self.assertTrue(w is not None)
