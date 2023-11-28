"""Test Local Storm Report parsing."""

import pytest
from pyiem.nws.products.lsr import parse_lsr, parser
from pyiem.util import get_test_file


@pytest.mark.parametrize("database", ["postgis"])
def test_snow_squall(dbcursor):
    """Test that snow squalls get ingested properly."""
    prod = parser(get_test_file("LSR/LSRBGM_snowsquall.txt"))
    assert len(prod.lsrs) == 1
    prod.lsrs[0].sql(dbcursor)
    dbcursor.execute(
        """SELECT type from lsrs_2023 WHERE
        valid = '2023-11-28 15:15+00' and wfo = 'BGM'
        and typetext = 'SNOW SQUALL'
        """
    )
    assert dbcursor.fetchone()["type"] == "q"


@pytest.mark.parametrize("database", ["postgis"])
def test_gh729_marine_wind(dbcursor):
    """Test support for mapping this type to marine wind gust."""
    prod = parser(get_test_file("LSR/LSRHGX_marine.txt"))
    prod.lsrs[0].sql(dbcursor)
    dbcursor.execute(
        """SELECT type from lsrs_2023 WHERE
        valid = '2023-06-11 04:09+00' and wfo = 'HGX'
        and typetext = 'TSTM WND GST'
        """
    )
    assert dbcursor.fetchone()["type"] == "M"


@pytest.mark.parametrize("database", ["postgis"])
def test_gh729_marine_hail(dbcursor):
    """Test support for mapping this type to marine wind gust."""
    prod = parser(get_test_file("LSR/LSRJAX_marinehail.txt"))
    prod.lsrs[0].sql(dbcursor)
    dbcursor.execute(
        """SELECT type from lsrs_2022 WHERE
        valid = '2022-04-02 18:50+00' and wfo = 'JAX'
        and typetext = 'HAIL'
        """
    )
    assert dbcursor.fetchone()["type"] == "h"


@pytest.mark.parametrize("database", ["postgis"])
def test_230605_fog(dbcursor):
    """Test support for fog LSRs with mile units."""
    prod = parser(get_test_file("LSR/LSR_fog.txt"))
    prod.lsrs[0].sql(dbcursor)
    dbcursor.execute(
        """SELECT product_id from lsrs_2023 WHERE
        valid = '2023-06-05 12:14+00' and wfo = 'GLD' and typetext = 'FOG'
        """
    )
    assert dbcursor.fetchone()["product_id"] == prod.get_product_id()


@pytest.mark.parametrize("database", ["postgis"])
def test_230508_summary_sql(dbcursor):
    """Test the new logic for inserting LSRs into the database."""
    data = get_test_file("LSR/LSR.txt")
    prod = parser(data.replace("SUMMARY", "Summary"))
    assert prod.is_summary()
    # Should insert a new entry
    prod.lsrs[0].sql(dbcursor)
    # Mark it as duplicated
    prod.lsrs[0].duplicate = True
    # Should now insert to product_id_summary column
    prod.lsrs[0].sql(dbcursor)
    dbcursor.execute(
        """SELECT product_id_summary from lsrs WHERE
        valid = '2013-07-22 20:01+00' and wfo = 'DMX' and typetext = 'HAIL'
        """
    )
    assert dbcursor.fetchone()["product_id_summary"] == prod.get_product_id()


def test_gh707_mixedcase():
    """Test that we properly handle mixed case LSR."""
    prod = parser(get_test_file("LSR/LSRICT_mixed.txt"))
    assert not prod.warnings
    j = prod.get_jabbers("")
    assert j[0][2]["channels"].index("LSR.TORNADO") > -1


@pytest.mark.parametrize("database", ["postgis"])
def test_220427_lsr_length(dbcursor):
    """Test the length of the tweet message is correct."""
    prod = parser(get_test_file("LSR/LSRKEY.txt"))
    j = prod.get_jabbers("http://localhost/")
    ans = (
        "At 6:58 AM EDT, 6 S Boca Chica [Gmz044 Co, FL] NWS EMPLOYEE reports "
        "WATER SPOUT. AN NWS EMPLOYEE REPRTED A WATERSPOUT THAT WAS VISIBLE "
        "FROM KEY WEST AROUND 7 AM EDT. IT LASTED AROUND 5 MINUTES.IT WAS "
        "REPORTED TO EXTEND HALFWAY DOWN FROM THE... #flwx "
        "http://localhost/#KEY/202204271058/202204271058"
    )
    assert j[0][2]["twitter"] == ans
    prod.lsrs[0].sql(dbcursor)


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
        "OVERPASSES ON HIGHWAY 83, FM1017, FM2686,... #txwx "
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
        "HAIL of 40 C. FAKED LSR FOR TESTING PURPOSES. #mswx "
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
        "STRIP MALL. SOME EXTERIOR WALLS COLLAPSED. #iawx "
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
