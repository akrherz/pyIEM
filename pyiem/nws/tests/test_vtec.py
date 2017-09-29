"""Unit tests for pyiem.nws.vtec"""
import unittest
import datetime

import pytz

from pyiem.nws import vtec


class TestVTEC(unittest.TestCase):
    """tests are a good thing, in general"""

    def test_fireweather(self):
        """Do we return different things for FW"""
        res = vtec.get_ps_string("FW", "A")
        self.assertEquals(res, "Fire Weather Watch")
        res = vtec.get_ps_string("FW", "W")
        self.assertEquals(res, "Red Flag Warning")

    def test_get_id(self):
        """check that getID() works as we expect"""
        vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        self.assertEqual(vc[0].get_id(2005), '2005-KJAN-TO-W-0130')

    def test_endstring(self):
        """Make sure that the end time string is empty for cancel action"""
        vc = vtec.parse("/O.CAN.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        self.assertEqual('', vc[0].get_end_string(None))

    def test_begints(self):
        """ check vtec.begints Parsing """
        vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        ts = datetime.datetime(2005, 8, 29, 16, 51)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(ts, vc[0].begints)

    def test_endts(self):
        """ check vtec.endts Parsing """
        vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        ts = datetime.datetime(2005, 8, 29, 18, 15)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(ts, vc[0].endts)

    def test_product_string(self):
        """ check vtec.product_string() formatting """
        vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        self.assertEqual("issues Tornado Warning", vc[0].product_string())
