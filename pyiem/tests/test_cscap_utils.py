from pyiem.cscap_utils import Worksheet
import unittest


class Test(unittest.TestCase):

    def test_worksheet(self):
        """Worksheet"""
        w = Worksheet(None)
        self.assertTrue(w is not None)
