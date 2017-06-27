import unittest
import datetime
import pytz

from pyiem import iemre


class TestIEMRE(unittest.TestCase):

    def test_simple(self):
        """ Get nulls for right and top values """
        i, j = iemre.find_ij(iemre.EAST, iemre.NORTH)
        assert i is None
        assert j is None

        i, j = iemre.find_ij(iemre.WEST, iemre.SOUTH)
        self.assertEqual(i, 0)
        self.assertEqual(j, 0)

    def test_hourly_offset(self):
        """ Compute the offsets """
        ts = datetime.datetime(2013, 1, 1, 0, 0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        offset = iemre.hourly_offset(ts)
        self.assertEqual(offset, 0)

        ts = datetime.datetime(2013, 1, 1, 6, 0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        ts = ts.astimezone(pytz.timezone("America/Chicago"))
        offset = iemre.hourly_offset(ts)
        self.assertEqual(offset, 6)

        ts = datetime.datetime(2013, 1, 5, 12, 0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        offset = iemre.hourly_offset(ts)
        self.assertEqual(offset, 4*24 + 12)

    def test_daily_offset(self):
        """ Compute the offsets """
        ts = datetime.datetime(2013, 1, 1, 0, 0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        offset = iemre.daily_offset(ts)
        self.assertEqual(offset, 0)

        ts = datetime.date(2013, 2, 1)
        offset = iemre.daily_offset(ts)
        self.assertEqual(offset, 31)

        ts = datetime.datetime(2013, 1, 5, 12, 0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        offset = iemre.daily_offset(ts)
        self.assertEqual(offset, 4)
