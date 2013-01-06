import unittest
import datetime

from pyiem.nws import hvtec
from pyiem import iemtz

class TestObservation(unittest.TestCase):
    
    def test_empty(self):
        """ check empty HVTEC Parsing """
        v = hvtec.parse("/00000.0.ER.000000T0000Z.000000T0000Z.000000T0000Z.OO/")
        self.assertEqual("00000", v[0].nwsli)

    def test_empty2(self):
        v = hvtec.parse("/NWYI3.0.ER.000000T0000Z.000000T0000Z.000000T0000Z.OO/")
        self.assertEqual("NWYI3", v[0].nwsli)
