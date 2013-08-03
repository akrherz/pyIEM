import unittest

from pyiem.nws.nwsli import NWSLI


class TestNWSLI(unittest.TestCase):
    
    def test_simple(self):
        """ See if we can generate a proper string from a UGCS """
        nwsli = NWSLI('AMWI4', 'Iowa All', ['DMX'], -99, 44)