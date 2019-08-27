"""test IEMRE stuff"""
import datetime
import pytz

import numpy as np
from pyiem.util import utc, get_dbconn
from pyiem import iemre


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


def test_get_grids():
    """Can we get grids?"""
    pgconn = get_dbconn("iemre")
    cursor = pgconn.cursor()
    valid = utc(2019, 12, 1, 1)
    cursor.execute(
        """
        DELETE from iemre_hourly_201912 WHERE valid = %s
    """,
        (valid,),
    )
    cursor.execute(
        """
        DELETE from iemre_hourly_201912 WHERE valid = %s
    """,
        (valid + datetime.timedelta(days=1),),
    )
    cursor.execute(
        """
        INSERT into iemre_hourly_201912
        (gid, valid, tmpk, dwpk, uwnd, vwnd, p01m)
        select gid, %s, random(), null, random(),
        random(), random() from iemre_grid LIMIT 100
    """,
        (valid,),
    )
    ds = iemre.get_grids(valid, varnames="tmpk", cursor=cursor)
    assert "tmpk" in ds
    assert "bogus" not in ds
    ds = iemre.get_grids(valid, cursor=cursor)
    assert np.isnan(ds["dwpk"].values.max())

    iemre.set_grids(valid, ds, cursor=cursor)
    iemre.set_grids(valid + datetime.timedelta(days=1), ds, cursor=cursor)


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
    assert offset == 4 * 24 + 12


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
