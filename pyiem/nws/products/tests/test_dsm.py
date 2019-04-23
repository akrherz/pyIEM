"""Test our DSM Parsing."""
import datetime

import pytest
import pytz
from pyiem.util import utc, get_test_file
from pyiem.nws.products.dsm import process, parser
from pyiem.util import get_dbconn


@pytest.fixture
def dbcursor():
    """Get a database cursor for testing."""
    cursor = get_dbconn('iem').cursor()
    # Create fake station, so we can create fake entry in summary
    # and current tables
    cursor.execute("""
        INSERT into stations(id, network, iemid, tzname)
        VALUES ('HKS', 'ZZ_ASOS', -100, 'UTC')
    """)
    cursor.execute("""
        INSERT into summary_2015(iemid, day) VALUES
        (-100, '2015-11-26')
    """)
    return cursor


@pytest.mark.parametrize("month", range(1, 13))
def test_simple(month):
    """Can we walk before we run."""
    text = (
        "KCVG DS 24/%02i 590353/ 312359// 53/ 48/"
        "/9470621/T/T/00/00/00/00/00/00/"
        "00/00/00/00/00/00/00/00/00/00/00/00/00/00/00/00/00/225/26381759/"
        "26500949="
    ) % (month, )
    tzprovider = {'KCVG': pytz.timezone("America/New_York")}
    dsm = process(text)
    dsm.compute_times(utc(2019, month, 25))
    dsm.tzlocalize(tzprovider['KCVG'])
    assert dsm.date == datetime.date(2019, month, 24)
    assert dsm.station == 'KCVG'
    assert dsm.time_sped_max == utc(2019, month, 24, 22, 59)


def test_collective(dbcursor):
    """Can we parse a collective."""
    prod = parser(get_test_file("DSM/DSM.txt"), utc(2015, 11, 26))
    assert not prod.warnings
    assert len(prod.data) == 23

    res = prod.sql(dbcursor)
    # first database insert should work from above
    assert res[0]


def test_190225_regress():
    """Parse something that failed RE."""
    text = (
        "KCUT DS 1100 25/02 061059/-040848//06/-03//0110442/"
        "T/00/00/00/00/00/00/00/00/00/00/T/-/-/-/-/-/-/-/-/-/-/-/-/-/-/"
        "08070124/10090103/18"
    )
    dsm = process(text)
    assert dsm is not None
    dsm.compute_times(utc(2019, 2, 25))
    assert dsm.station == 'KCUT'


def test_190225_badtime():
    """This should not trip us up."""
    text = (
        "KMMV DS 1500 05/02 361459/ 250741// 36/ 25//9740006/01/T/T/01/T/00/"
        "00/00/00/00/00/00/00/00/00/00/-/-/-/-/-/-/-/-/-/-/04090030/211750614/"
        "1="
    )
    dsm = process(text)
    assert dsm is not None
    dsm.compute_times(utc(2019, 2, 5))
    assert dsm.station == 'KMMV'
