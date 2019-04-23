"""test IEMRE stuff"""
import datetime
import pytz

from pyiem.util import utc
from pyiem import iemre


def test_simple():
    """ Get nulls for right and top values """
    i, j = iemre.find_ij(iemre.EAST, iemre.NORTH)
    assert i is None
    assert j is None

    i, j = iemre.find_ij(iemre.WEST, iemre.SOUTH)
    assert i == 0
    assert j == 0


def test_hourly_offset():
    """ Compute the offsets """
    ts = utc(2013, 1, 1, 0, 0)
    offset = iemre.hourly_offset(ts)
    assert offset == 0

    ts = utc(2013, 1, 1, 6, 0)
    ts = ts.astimezone(pytz.timezone("America/Chicago"))
    offset = iemre.hourly_offset(ts)
    assert offset == 6

    ts = utc(2013, 1, 5, 12, 0)
    offset = iemre.hourly_offset(ts)
    assert offset == 4*24 + 12


def test_daily_offset():
    """ Compute the offsets """
    ts = utc(2013, 1, 1, 0, 0)
    offset = iemre.daily_offset(ts)
    assert offset == 0

    ts = datetime.date(2013, 2, 1)
    offset = iemre.daily_offset(ts)
    assert offset == 31

    ts = utc(2013, 1, 5, 12, 0)
    offset = iemre.daily_offset(ts)
    assert offset == 4
