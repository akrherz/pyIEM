"""test IEMRE stuff"""
import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import numpy as np
from pyiem.util import utc, get_dbconn
from pyiem import iemre


def test_api():
    """Test some aux methods."""
    assert iemre.get_dailyc_mrms_ncname() is not None
    assert iemre.get_dailyc_ncname() is not None


def test_ncname():
    """Test the responses for get_names."""
    assert iemre.get_daily_ncname(2020) is not None
    assert iemre.get_hourly_ncname(2020) is not None
    assert iemre.get_daily_mrms_ncname(2020) is not None


def test_get_table():
    """Test get_table."""
    d1 = datetime.date(2000, 8, 1)
    assert iemre.get_table(d1) == "iemre_daily_2000"
    d2 = utc(2000, 9, 1, 12)
    assert iemre.get_table(d2) == "iemre_hourly_200009"


def test_get_gid():
    """Can we get a gid?"""
    assert iemre.get_gid(-96, 44) is not None


def test_forecast_grids():
    """Test getting and setting grids from the future."""
    pgconn = get_dbconn("iemre")
    cursor = pgconn.cursor()
    valid = datetime.date(2029, 12, 1)
    cursor.execute(
        """
        DELETE from iemre_daily_forecast WHERE valid = %s
    """,
        (valid,),
    )
    cursor.execute(
        """
        INSERT into iemre_daily_forecast
        (gid, valid, high_tmpk, low_tmpk, p01d, rsds)
        select gid, %s, random(), random(),
        random(), random() from iemre_grid LIMIT 100
    """,
        (valid,),
    )
    ds = iemre.get_grids(valid, cursor=cursor, table="iemre_daily_forecast")
    assert "high_tmpk" in ds
    assert "bogus" not in ds

    iemre.set_grids(valid, ds, cursor=cursor, table="iemre_daily_forecast")


def test_simple():
    """Get nulls for right and top values"""
    i, j = iemre.find_ij(iemre.EAST, iemre.NORTH)
    assert i is None
    assert j is None

    i, j = iemre.find_ij(iemre.WEST, iemre.SOUTH)
    assert i == 0
    assert j == 0


def test_hourly_offset():
    """Compute the offsets"""
    ts = utc(2013, 1, 1, 0, 0)
    offset = iemre.hourly_offset(ts)
    assert offset == 0

    ts = utc(2013, 1, 1, 6, 0)
    ts = ts.astimezone(ZoneInfo("America/Chicago"))
    offset = iemre.hourly_offset(ts)
    assert offset == 6

    ts = utc(2013, 1, 5, 12, 0)
    offset = iemre.hourly_offset(ts)
    assert offset == 4 * 24 + 12


def test_daily_offset():
    """Compute the offsets"""
    ts = utc(2013, 1, 1, 0, 0)
    offset = iemre.daily_offset(ts)
    assert offset == 0

    ts = datetime.date(2013, 2, 1)
    offset = iemre.daily_offset(ts)
    assert offset == 31

    ts = utc(2013, 1, 5, 12, 0)
    offset = iemre.daily_offset(ts)
    assert offset == 4
