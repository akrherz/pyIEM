"""Test Observation"""
# pylint: disable=redefined-outer-name
import string
import datetime
import random

import psycopg2.extras
import numpy as np
import pytest
import pandas as pd
from pyiem import observation
from pyiem.util import get_dbconn, utc


class blah:
    """pass"""

    iemid = None
    ob = None
    conn = None
    cursor = None


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
    with pytest.warns(None) as record:
        ob = observation.Observation("XXX", "XXX", ts)
    assert not record
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
    with pytest.warns(None) as record:
        assert observation.bounded(val, 0, 100) == expected
    assert not record.list


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
    res.conn = get_dbconn("iem")
    res.cursor = res.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
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
    assert iemob.cursor.fetchone()[0] == 55
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
    assert iemob.cursor.fetchone()[0] == 54


def test_settting_null(iemob):
    """Test setting a null value into the database after a real value."""
    iemob.ob.data["max_tmpf"] = 55
    iemob.ob.save(iemob.cursor)
    iemob.cursor.execute(
        """SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""",
        (iemob.iemid,),
    )
    assert iemob.cursor.fetchone()[0] == 55
    iemob.ob.data["null_max_tmpf"] = None
    iemob.ob.save(iemob.cursor)
    iemob.cursor.execute(
        """SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""",
        (iemob.iemid,),
    )
    assert iemob.cursor.fetchone()[0] is None


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
    response = iemob.ob.save(iemob.cursor)
    assert iemob.ob.data["dwpf"] is None
    iemob.ob.data["relh"] = 50
    response = iemob.ob.save(iemob.cursor)
    assert abs(iemob.ob.data["dwpf"] - 36.71) < 0.2
    iemob.cursor.execute(
        """SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""",
        (iemob.iemid,),
    )
    assert iemob.cursor.rowcount == 1
    assert iemob.cursor.fetchone()[0] == 55


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
