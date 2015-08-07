import unittest
from pyiem import util


class TestUtil(unittest.TestCase):

    def test_properties(self):
        """ Try the properties function"""
        prop = util.get_properties()
        self.assertTrue(isinstance(prop, dict))

    def test_drct2text(self):
        """ Test conversion of drct2text """
        self.assertEquals(util.drct2text(360), "N")
        self.assertEquals(util.drct2text(90), "E")
        # A hack to get move coverage
        for i in range(360):
            util.drct2text(i)
