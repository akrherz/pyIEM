"""test IEMRE stuff"""
import datetime
from zoneinfo import ZoneInfo

from pyiem import database, iemre
from pyiem.util import utc


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
    assert iemre.get_gid(-960, 440) is None


def test_writing_grids():
    """Test letting the API write data from the future."""
    pgconn = database.get_dbconn("iemre")
    cursor = pgconn.cursor()
    valid = datetime.date.today() + datetime.timedelta(days=120)
    ds = iemre.get_grids(valid, varnames=["high_tmpk"])
    iemre.set_grids(valid, ds)
    ds = iemre.get_grids(valid, varnames=["high_tmpk"])
    assert ds["high_tmpk"].lat[0] > 0
    # Cleanup after ourself
    cursor.execute(
        f"DELETE from iemre_daily_{valid:%Y} WHERE valid = %s",
        (valid,),
    )
    cursor.close()
    pgconn.commit()


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
