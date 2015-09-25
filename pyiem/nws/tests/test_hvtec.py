import unittest
from pyiem.nws import hvtec


class TestObservation(unittest.TestCase):

    def test_badtime(self):
        """Make sure contime errors"""
        v = hvtec.contime("BAD")
        self.assertTrue(v is None)

    def test_empty(self):
        """ check empty HVTEC Parsing """
        v = hvtec.parse(
            "/00000.0.ER.000000T0000Z.000000T0000Z.000000T0000Z.OO/")
        self.assertEqual("00000", v[0].nwsli.id)

    def test_empty2(self):
        initial = "/NWYI3.0.ER.000000T0000Z.000000T0000Z.000000T0000Z.OO/"
        v = hvtec.parse(initial)
        self.assertEqual("NWYI3", v[0].nwsli.id)
        self.assertEqual(str(v[0]), initial)
