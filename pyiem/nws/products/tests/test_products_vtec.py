"""Test some of the atomic stuff in the VTEC module"""
import unittest
import datetime

from pyiem.nws.products.vtec import check_dup_ps
from pyiem.nws.vtec import parse


class FakeObject(object):
    """Mocked thing"""
    pass


class TestVTEC(unittest.TestCase):
    """Test All Things!"""

    def test_dups(self):
        """We had a false positive :("""
        segment = FakeObject()
        segment.tp = FakeObject()
        segment.tp.valid = datetime.datetime(2017, 5, 24, 12, 0)
        segment.vtec = parse((
            '/O.UPG.KTWC.FW.A.0008.170525T1800Z-170526T0300Z/\n'
            '/O.NEW.KTWC.FW.W.0013.170525T1800Z-170526T0300Z/\n'
            '/O.UPG.KTWC.FW.A.0009.170526T1700Z-170527T0300Z/\n'
            '/O.NEW.KTWC.FW.W.0014.170526T1700Z-170527T0300Z/\n'))
        res = check_dup_ps(segment)
        self.assertFalse(res)
