"""Test Local Storm Report parsing."""
# pylint: disable=redefined-outer-name

import pytest
from pyiem.util import get_test_file, get_dbconn
from pyiem.nws.products.lsr import parser, parse_lsr


@pytest.fixture
def dbcursor():
    """Database cursor."""
    return get_dbconn("postgis").cursor()


def test_unknown_units():
    """Test what happens when we have unknown units."""
    prod = parser(get_test_file("LSR/LSRJAN_fakeunits.txt"))
    assert str(prod.lsrs[0])
    j = prod.get_jabbers("")
    ans = (
        "At 11:37 AM CST, Yokena [Warren Co, MS] AMATEUR RADIO reports "
        "HAIL of 40 C. FAKED LSR FOR TESTING PURPOSES. "
        "#JAN/201912161737/201912161737"
    )
    assert j[0][2]["twitter"] == ans


def test_summary():
    """Test that our summary logic works."""
    prod = parser(get_test_file("LSR/LSR.txt"))
    j = prod.get_jabbers("")
    prod.lsrs[0].duplicate = True
    prod.duplicates = 1
    j2 = prod.get_jabbers("")
    assert (len(j) - len(j2)) == 1


def test_issue320_badmnd():
    """Test we can deal with a bad MND timestamp header."""
    prod = parser(get_test_file("LSR/LSRTBW_badmnd.txt"))
    assert prod.z is not None


def test_issue320_reallybadmnd():
    """Test what happens when we have no workable MND."""
    prod = parser(get_test_file("LSR/LSRTBW_badmnd.txt").replace("NOV 12", ""))
    assert prod.z is None
    assert not prod.lsrs


def test_200913_nounits():
    """Test that we properly handle LSRs without units."""
    prod = parser(get_test_file("LSR/LSRCRP.txt"))
    assert not prod.warnings


def test_empty():
    """Test that we can handle an empty LSR."""
    prod = parser(get_test_file("LSR/LSR_empty.txt"))
    res = prod.get_temporal_domain()
    assert res[0] is None and res[1] is None


def test_too_short():
    """Test a psuedo too short LSR."""
    prod = parser(get_test_file("LSR/LSRDVN_old.txt"))
    res = parse_lsr(prod, "")
    assert res is None


def test_duplicate():
    """Test that we can mark a LSR as a duplicate."""
    prod = parser(get_test_file("LSR/LSRDVN_old.txt"))
    j = prod.get_jabbers("")
    assert len(j) == 1
    prod.lsrs[0].duplicate = True
    j = prod.get_jabbers("")
    assert not j


def test_issue277_oldlsr():
    """Test the tweet generated from a delayed LSR."""
    prod = parser(get_test_file("LSR/LSRDVN_old.txt"))
    assert len(prod.lsrs) == 1
    j = prod.get_jabbers("")
    ans = (
        "[Delayed Report] On Aug 10, at 12:28 PM CDT, 3 WSW Cedar Rapids "
        "[Linn Co, IA] PUBLIC reports "
        "TSTM WND GST of E130 MPH. ROOF REMOVED FROM SMALL "
        "STRIP MALL. SOME EXTERIOR WALLS COLLAPSED. "
        "#DVN/202008101728/202008101728"
    )
    assert j[0][2]["twitter"] == ans


def test_sql(dbcursor):
    """Test that we can insert into the database."""
    prod = parser(get_test_file("LSR/LSRDVN_old.txt"))
    assert prod.lsrs
    for lsr in prod.lsrs:
        lsr.sql(dbcursor)
        assert dbcursor.rowcount == 1


def test_issue170_nan():
    """How are we handling LSRs that have bad NAN magnitudes."""
    prod = parser(get_test_file("LSR/LSRJAN_NAN.txt"))
    assert len(prod.warnings) == 1
    assert not prod.lsrs


def test_issue61_future():
    """Can we properly warn on a product from the future."""
    prod = parser(get_test_file("LSR/LSRGSP_future.txt"))
    assert len(prod.warnings) == 1
    assert not prod.lsrs
