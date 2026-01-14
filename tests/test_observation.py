"""Test Observation"""

# pylint: disable=redefined-outer-name
import datetime
import random
import string
import warnings

import numpy as np
import pandas as pd
import pytest

from pyiem import observation
from pyiem.database import get_dbconnc
from pyiem.util import utc


class blah:
    """pass"""

    iemid = None
    ob = None
    conn = None
    cursor = None


def test_gigo_converted_to_none():
    """Test that our observation bounds work."""
    ob = observation.Observation("XXX", "XXX", utc())
    ob.data["tmpf"] = -9999.0
    assert ob.data["tmpf"] is None


def test_bounded_non_scalar():
    """Test that we get a runtime exception with this."""
    with pytest.raises(RuntimeError):
        observation.bounded(np.array([1, 2, 3]), 0, 100)


def test_bounded_invalid_str():
    """Test that we get a None when given a bad string."""
    assert observation.bounded("M", 0, 10) is None


def test_numpy_datetime64():
    """Test that numpy's datetime64 is not considered as daily."""
    ts = np.datetime64("2020-12-30")
    with pytest.warns(UserWarning):
        ob = observation.Observation("XXX", "XXX", ts)
    assert ob.data["_isdaily"] is False
    assert ob.data["valid"] == utc(2020, 12, 30)


def test_date_isdaily():
    """Test that providing a date triggers the isdaily logic."""
    ts = datetime.date(2020, 12, 30)
    with warnings.catch_warnings(record=True) as w:
        ob = observation.Observation("XXX", "XXX", ts)
    assert not w
    assert ob.data["_isdaily"] is True
    assert ob.data["valid"] == ts


def test_pandas_timestamp():
    """Test that Pandas Timestamp objects are not considered as daily."""
    ts = pd.Timestamp("2020/12/30")
    with pytest.warns(UserWarning):
        ob = observation.Observation("XXX", "XXX", ts)
    assert ob.data["_isdaily"] is False
    assert ob.data["valid"] == utc(2020, 12, 30)


def test_pandas_timestamp_tz():
    """Test that Pandas Timestamp tz objects are not considered as daily."""
    ts = pd.Timestamp("2020/12/30", tz="America/Chicago")
    ob = observation.Observation("XXX", "XXX", ts)
    assert ob.data["_isdaily"] is False
    assert ob.data["valid"] == utc(2020, 12, 30, 6)


@pytest.mark.parametrize(
    "val, expected",
    [
        (np.nan, None),
        (np.ma.array(1, mask=True), None),
        (None, None),
        (10, 10),
        (np.ma.array(1, mask=False), 1),
        (101, None),
        (-1, None),
    ],
)
def test_bounded(val, expected):
    """Test that our bounded function works and does not raise Warnings."""
    with warnings.catch_warnings(record=True) as w:
        assert observation.bounded(val, 0, 100) == expected
    assert not w


def test_calc():
    """Can we compute feels like and RH?"""
    ts = utc(2018)
    ob = observation.Observation("FAKE", "FAKE", ts)
    ob.data["tmpf"] = 89.0
    ob.data["dwpf"] = 70.0
    ob.data["sknt"] = 10.0
    ob.calc()
    assert (ob.data["feel"] - 94.3) < 0.1
    assert (ob.data["relh"] - 53.6) < 0.1


def test_gh623_feelslike_without_wind():
    """Test that we can compute feelslike without wind speed."""
    ts = utc(2018)
    ob = observation.Observation("FAKE", "FAKE", ts)
    ob.data["tmpf"] = 89.0
    ob.data["dwpf"] = 70.0
    ob.calc()
    assert (ob.data["feel"] - 94.3) < 0.1
    ob = observation.Observation("FAKE", "FAKE", ts)
    ob.data["tmpf"] = -19.0
    ob.data["dwpf"] = -22.0
    ob.calc()
    assert ob.data["feel"] is None


@pytest.fixture
def iemob():
    """Database."""
    res = blah()
    ts = utc(2015, 9, 1, 1, 0)
    sid = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    res.iemid = 0 - random.randint(0, 1000)
    res.ob = observation.Observation(sid, "FAKE", ts)
    res.conn, res.cursor = get_dbconnc("iem")
    # Create fake station, so we can create fake entry in summary
    # and current tables
    res.cursor.execute(
        "INSERT into stations(id, network, iemid, tzname) "
        "VALUES (%s, 'FAKE', %s, 'UTC')",
        (sid, res.iemid),
    )
    res.cursor.execute(
        "INSERT into current(iemid, valid) VALUES (%s, '2015-09-01 00:00+00')",
        (res.iemid,),
    )
    res.cursor.execute(
        "INSERT into summary_2015(iemid, day) VALUES (%s, '2015-09-01')",
        (res.iemid,),
    )
    return res


def test_notz():
    """Test that we warn when there is no timezone set."""
    msg = "tzinfo is not set on valid, defaulting to UTC"
    with pytest.warns(UserWarning, match=msg):
        observation.Observation("Z", "Z", datetime.datetime(2000, 1, 1))


def test_nodata(iemob):
    """Make sure we return False when we don't have entries in tables"""
    iemob.ob.data["station"] = "HaHaHa"
    response = iemob.ob.save(iemob.cursor)
    assert not response

    response = iemob.ob.load(iemob.cursor)
    assert not response


def test_hardcoded_maxtmpf(iemob):
    """Do we do the right thing when max_tmpf is set."""
    iemob.ob.data["tmpf"] = 55
    assert iemob.ob.save(iemob.cursor, skip_current=True)
    # in the database max_tmpf should be 55 now
    iemob.cursor.execute(
        """
        SELECT max_tmpf from summary_2015
        WHERE day = '2015-09-01' and iemid = %s
    """,
        (iemob.iemid,),
    )
    assert iemob.cursor.fetchone()["max_tmpf"] == 55
    # setting max_tmpf to 54 should update it too
    iemob.ob.data["max_tmpf"] = 54
    assert iemob.ob.save(iemob.cursor)
    iemob.cursor.execute(
        """
        SELECT max_tmpf from summary_2015
        WHERE day = '2015-09-01' and iemid = %s
    """,
        (iemob.iemid,),
    )
    assert iemob.cursor.fetchone()["max_tmpf"] == 54


def test_setting_null(iemob):
    """Test setting a null value into the database after a real value."""
    iemob.ob.data["max_tmpf"] = 55
    iemob.ob.save(iemob.cursor)
    iemob.cursor.execute(
        """SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""",
        (iemob.iemid,),
    )
    assert iemob.cursor.fetchone()["max_tmpf"] == 55
    iemob.ob.data["null_max_tmpf"] = None
    # bogus value that should not trip up the summary table update
    iemob.ob.data["null_drct"] = None
    iemob.ob.save(iemob.cursor)
    iemob.cursor.execute(
        """SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""",
        (iemob.iemid,),
    )
    assert iemob.cursor.fetchone()["max_tmpf"] is None


def test_newdate(iemob):
    """Test that we can add a summary table entry."""
    iemob.ob.data["valid"] = iemob.ob.data["valid"].replace(day=2)
    assert iemob.ob.save(iemob.cursor) is True

    tomorrow = datetime.date.today() + datetime.timedelta(days=2)
    iemob.ob.data["valid"] = iemob.ob.data["valid"].replace(
        year=tomorrow.year, month=tomorrow.month, day=tomorrow.day
    )
    assert iemob.ob.save(iemob.cursor) is False


def test_null(iemob):
    """Make sure our null logic is working"""
    iemob.ob.data["tmpf"] = 55
    response = iemob.ob.save(iemob.cursor)
    assert response
    assert iemob.ob.data["dwpf"] is None
    iemob.ob.data["relh"] = 0
    iemob.ob.save(iemob.cursor)
    assert iemob.ob.data["dwpf"] is None
    iemob.ob.data["relh"] = 50
    iemob.ob.save(iemob.cursor)
    assert abs(iemob.ob.data["dwpf"] - 36.71) < 0.2
    iemob.cursor.execute(
        """SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""",
        (iemob.iemid,),
    )
    assert iemob.cursor.rowcount == 1
    assert iemob.cursor.fetchone()["max_tmpf"] == 55


def test_update(iemob):
    """Make sure we can update the database"""
    response = iemob.ob.load(iemob.cursor)
    assert not response
    iemob.ob.data["valid"] = iemob.ob.data["valid"].replace(hour=0)
    response = iemob.ob.load(iemob.cursor)
    assert response

    response = iemob.ob.save(iemob.cursor)
    assert response

    response = iemob.ob.save(iemob.cursor, force_current_log=True)
    assert response


def test_which_table():
    """See that we get back the right summary table."""
    f = observation.get_summary_table
    assert f(None) == "summary"
    assert f(datetime.date(2019, 1, 1)) == "summary"
    assert f(datetime.datetime(2019, 1, 1)) == "summary"
    assert f(datetime.date(2019, 4, 1)) == "summary_2019"
