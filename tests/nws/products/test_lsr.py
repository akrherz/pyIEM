"""Test Local Storm Report parsing."""

import pytest
from pyiem.util import get_test_file
from pyiem.nws.products.lsr import parser, parse_lsr


def test_220204_bad_ice_totals():
    """Test we don't get false positives here."""
    prod = parser(get_test_file("LSR/LSRPAH_ice.txt"))
    assert prod.lsrs[0].magnitude_f == 0.25
    prod = parser(get_test_file("LSR/LSRPAH_ice2.txt"))
    assert prod.lsrs[0].magnitude_f is None


def test_issue406_empty():
    """Test that we emit warnings for missing counties/states."""
    text = get_test_file("LSR/LSRAJK.txt")
    prod = parser(text)
    assert len(prod.warnings) == 3
    prod = parser(text.replace("TRAINED SPOTTER", "               "))
    assert len(prod.warnings) == 4


def test_tweetlen():
    """Test that our tweet is not too long!"""
    prod = parser(get_test_file("LSR/LSRBRO.txt"))
    j = prod.get_jabbers("")
    ans = (
        "At 12:45 AM CST, RIO Grande City [Starr Co, TX] DEPT OF HIGHWAYS "
        "reports FREEZING RAIN of U0.00 INCH. MULTIPLE REPORTS RECEIVED VIA "
        "DRIVETEXAS.ORG OF ICE AND SNOW ACCUMLATION OCCURRING ON BRIDGES AND "
        "OVERPASSES ON HIGHWAY 83, FM1017, FM2686, FM2294, F... "
        "#BRO/202102150645/202102150645"
    )
    assert j[0][2]["twitter"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_icestorm(dbcursor):
    """Test that we guess the ice storm magnitude and units."""
    prod = parser(get_test_file("LSR/LSRTOP_ICE.txt"))
    assert prod.lsrs[0].magnitude_f == 0.20
    j = prod.get_jabbers("")
    assert j[0][0].find("ICE STORM of 0.20 INCH") > -1
    prod.lsrs[0].sql(dbcursor)


def test_issue331_state_channels():
    """Test that we assign new state based channels to LSRs."""
    prod = parser(get_test_file("LSR/LSRFSD.txt"))
    j = prod.get_jabbers("")
    channels = j[0][2]["channels"].split(",")
    assert "LSR.SD.TORNADO" in channels
    assert "LSR.SD" in channels


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


@pytest.mark.parametrize("database", ["postgis"])
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
