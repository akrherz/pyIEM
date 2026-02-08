"""Test our DSM Parsing."""

import datetime
from zoneinfo import ZoneInfo

import pytest

from pyiem.nws.products.dsm import compute_time, parser, process
from pyiem.util import get_test_file, utc


def create_entries(cursor):
    """Get a database cursor for testing."""
    # Create fake station, so we can create fake entry in summary
    # and current tables
    cursor.execute(
        "INSERT into stations(id, network, iemid, tzname) "
        "VALUES ('HKS', 'ZZ_ASOS', -100, 'UTC')"
    )
    cursor.execute(
        "INSERT into summary_2015(iemid, day) VALUES (-100, '2015-11-26')"
    )


def test_get_jabbers():
    """Test the jabber message generation."""
    prod = parser(get_test_file("DSM/DSM.txt"), utc(2015, 11, 26))
    # Goose values to complete coverage on _pformat
    prod.data[3].groupdict["pday"] = "-"
    prod.data[4].groupdict["pday"] = None
    prod.data[5].groupdict["pday"] = "T"
    prod.data[6].groupdict["pday"] = "P6"
    jmsgs = prod.get_jabbers("https://iem.local")
    assert len(jmsgs) == 23
    assert jmsgs[21][2]["channels"] == "DSMDCU"
    ans = (
        "KPBF Nov 26 Daily Summary Message: High: 63 Low: 45 Precip: 0.01 "
        "https://iem.local?pid=201511270616-KZME-CDUS27-DSMPBF"
    )
    assert jmsgs[12][0] == ans


def test_231005_kjef():
    """Test something found in the wild."""
    text = (
        "KJEF DS 04/10 7714436/-326960014// 77/ 66//9901719/-10/00/00/00/00/"
        "00/00/00/04/03/01/00/00/-51199/00/00/00/00/00/00/00/00/00/00/00/M/"
        "-3260141304/20-2414027/1/NN/N/N/NN/ET EP EW="
    )
    dsm = process(text)
    assert dsm is None


def test_none_compute_time():
    """Test we can handle a none."""
    assert compute_time(datetime.date(2000, 1, 1), None) is None


def test_kadf():
    """Test that a stray space does not mess us up."""
    text = """
882 
CDUS27 KZME 301207
KADF DS 0605 30/12  330019/ 200605// 43/ 20//0470213/00/00/-/-/-/-/-/
-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/07/34090000/32130006/-/NN/N/N/NN/ET=
"""
    prod = parser(text, utcnow=utc(2025, 12, 30, 12, 16))
    assert prod.data[0].date == datetime.date(2025, 12, 30)


def test_jan1():
    """Test that a DSM for the previous year works properly."""
    text = """
794
CDUS27 KZME 010616
KHKS DS 31/12 661152/ 470316// 66/ 46//0021509/45/00/00/00/00/00/05/
02/06/T/T/12/00/03/17/T/T/T/00/00/00/00/T/00/00/78/17171245/16231238/
13/NN/N/N/NN/ET EP EW=
"""
    prod = parser(text, utcnow=utc(2021, 1, 1, 6, 16))
    assert prod.data[0].date == datetime.date(2020, 12, 31)


def test_junk():
    """Test that we gracefully handle GIGO."""
    text = "000 \nCDUS27 KISU 020200\nBLAH BLAH=\nBLAH BLAH BLAH=\n"
    prod = parser(text)
    assert prod.warnings


@pytest.mark.parametrize("month", range(1, 13))
def test_simple(month):
    """Can we walk before we run."""
    text = (
        "KCVG DS 24/%02i 590353/ 312359// 53/ 48/"
        "/9470621/T/T/00/00/00/00/00/00/"
        "00/00/00/00/00/00/00/00/00/00/00/00/00/00/00/00/00/225/26381759/"
        "26500949="
    ) % (month,)
    tzprovider = {"KCVG": ZoneInfo("America/New_York")}
    dsm = process(text)
    dsm.compute_times(utc(2019, month, 25))
    dsm.time_sped_gust_max = None
    dsm.tzlocalize(tzprovider["KCVG"])
    assert dsm.date == datetime.date(2019, month, 24)
    assert dsm.station == "KCVG"
    assert dsm.time_sped_max == utc(2019, month, 24, 22, 59)


@pytest.mark.parametrize("database", ["iem"])
def test_collective(dbcursor):
    """Can we parse a collective."""
    create_entries(dbcursor)
    prod = parser(get_test_file("DSM/DSM.txt"), utc(2015, 11, 26))
    assert not prod.warnings
    assert len(prod.data) == 23

    res = prod.sql(dbcursor)
    # first database insert should work from above
    assert res[0]

    # See what got written to the database as a report
    dbcursor.execute(
        "SELECT report from summary_2015 where iemid = -100 and "
        "day = '2015-11-26'"
    )
    ans = "201511270616-KZME-CDUS27-DSMHKS"
    assert dbcursor.fetchone()["report"] == ans

    # send it again to test the string append
    assert prod.sql(dbcursor)[0]
    dbcursor.execute(
        "SELECT report from summary_2015 where iemid = -100 and "
        "day = '2015-11-26'"
    )
    assert dbcursor.fetchone()["report"] == f"{ans} {ans}"


@pytest.mark.parametrize("database", ["iem"])
def test_allmissing(dbcursor):
    """Test that we hit some code."""
    now = utc(2015, 11, 27, 7)
    prod = parser(get_test_file("DSM/DSM_allmissing.txt"), now)
    tzprovider = {"KHKS": ZoneInfo("America/New_York")}
    prod.tzlocalize(tzprovider)
    assert prod.sql(dbcursor)[0] is False


def test_200824_refail():
    """Test a RE parse failure."""
    text = (
        "KHEI DS 1500 23/08 M/M// 86/M//7061455/00/00/00/00/00/00/00/00/00/00/"
        "00/00/00/00/00/00/-187/-51/-/-/-/-/-/-/-/-/06231121/05311119="
    )
    dsm = process(text)
    assert dsm is not None


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
    assert dsm.station == "KCUT"


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
    assert dsm.station == "KMMV"
