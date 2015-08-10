import unittest
import datetime
import pytz

from pyiem.nws import vtec


class TestObservation(unittest.TestCase):

    def test_getID(self):
        ''' check that getID() works as we expect '''
        v = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        self.assertEqual(v[0].getID(2005), '2005-KJAN-TO-W-0130')

    def test_endstring(self):
        ''' Make sure that the end time string is empty for cancel action '''
        v = vtec.parse("/O.CAN.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        self.assertEqual('', v[0].get_end_string(None))

    def test_begints(self):
        """ check vtec.begints Parsing """
        v = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        ts = datetime.datetime(2005, 8, 29, 16, 51)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(ts, v[0].begints)

    def test_endts(self):
        """ check vtec.endts Parsing """
        v = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        ts = datetime.datetime(2005, 8, 29, 18, 15)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(ts, v[0].endts)

    def test_product_string(self):
        """ check vtec.product_string() formatting """
        v = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
        self.assertEqual("issues Tornado Warning", v[0].product_string())
