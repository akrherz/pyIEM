"""MCD/MPD tests."""

import pytest
from pyiem.exceptions import MCDException
from pyiem.nws.products import parser
from pyiem.util import utc, get_test_file


def test_gh528_concerning():
    """Test how we deal with the MPD concerning field."""
    orig = get_test_file("MCD_MPD/MPD_noconfidence.txt")
    prod = parser(orig)
    assert prod.concerning == "Heavy rainfall"


def test_exceptions():
    """Test that various things lead to exceptions."""
    orig = get_test_file("MCD_MPD/SWOMCD.txt")
    with pytest.raises(MCDException):
        parser(orig.replace("LAT...LON", "BLAH"))
    # See if -40 logic works
    parser(orig.replace("44738786", "44733786"))

    prod = parser(orig.replace("CONCERNING", "BLAH"))
    assert prod.concerning is None

    prod = parser(orig.replace("VALID", "BLAH"))
    assert prod.warnings

    with pytest.raises(MCDException):
        parser(orig.replace("DISCUSSION", "BLAH"))
    with pytest.raises(MCDException):
        parser(orig.replace("ATTN...WFO", "BLAH"))


def test_datetime_coverage():
    """Test products that cross the first of the month."""
    assert parser(get_test_file("MCD_MPD/SWOMCD_sep1.txt")) is not None


@pytest.mark.parametrize("database", ["postgis"])
def test_issue163(dbcursor):
    """Test parsing of the concerning tag."""
    prod = parser(get_test_file("MCD_MPD/SWOMCDconcerning.txt"))
    prod.database_save(dbcursor)
    dbcursor.execute(
        "SELECT concerning from mcd where product_id = %s",
        (prod.get_product_id(),),
    )
    ans = "Severe Thunderstorm Watch 60"
    assert dbcursor.fetchone()[0] == ans
    # Exercise that the remove worked.
    prod.database_save(dbcursor)
    dbcursor.execute(
        "SELECT count(*) from mcd where product_id = %s",
        (prod.get_product_id(),),
    )
    assert dbcursor.fetchone()[0] == 1


@pytest.mark.parametrize("database", ["postgis"])
def test_170926_nodbinsert(dbcursor):
    """This product never hit the database for some reason?"""
    prod = parser(get_test_file("MCD_MPD/SWOMCD_2010.txt"))
    prod.database_save(dbcursor)
    dbcursor.execute(
        "SELECT * from mcd where product_id = %s",
        (prod.get_product_id(),),
    )
    assert dbcursor.rowcount == 1


@pytest.mark.parametrize("database", ["postgis"])
def test_mpd_mcdparser(dbcursor):
    """The mcdparser can do WPC's MPD as well, test it"""
    prod = parser(get_test_file("MCD_MPD/MPD.txt"))
    assert abs(prod.geometry.area - 4.657) < 0.001
    assert prod.attn_wfo == ["PHI", "AKQ", "CTP", "LWX"]
    assert prod.attn_rfc == ["MARFC"]
    ans = (
        "#WPC issues MPD 98 concerning "
        "HEAVY RAINFALL...FLASH FLOODING POSSIBLE: NRN VA...D.C"
        "....CENTRAL MD INTO SERN PA "
        "https://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php"
        "?md=98&yr=2013"
    )
    assert prod.tweet() == ans
    ans = (
        "Weather Prediction Center issues "
        "Mesoscale Precipitation Discussion #98 concerning HEAVY RAINFALL"
        "...FLASH FLOODING POSSIBLE"
        " https://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php"
        "?md=98&amp;yr=2013"
    )
    assert prod.get_jabbers("http://localhost")[0][0] == ans
    prod.database_save(dbcursor)


@pytest.mark.parametrize("database", ["postgis"])
def test_mcdparser(dbcursor):
    """Test Parsing of MCD Product"""
    prod = parser(get_test_file("MCD_MPD/SWOMCD.txt"))
    assert abs(prod.geometry.area - 4.302) < 0.001
    assert prod.discussion_num == 1525
    assert prod.attn_wfo[2] == "DLH"
    ans = "PORTIONS OF NRN WI AND THE UPPER PENINSULA OF MI"
    assert prod.areas_affected == ans

    # With probability this time
    prod = parser(get_test_file("MCD_MPD/SWOMCDprob.txt"))
    assert abs(prod.geometry.area - 2.444) < 0.001
    assert prod.watch_prob == 20

    jmsg = prod.get_jabbers("http://localhost")
    ans = (
        "<p>Storm Prediction Center issues "
        '<a href="https://www.spc.noaa.gov/'
        'products/md/2013/md1678.html">Mesoscale Discussion #1678</a> '
        "concerning SEVERE POTENTIAL...WATCH UNLIKELY "
        "[watch probability: 20%] "
        '(<a href="http://localhost'
        '?pid=201308091725-KWNS-ACUS11-SWOMCD">View text</a>)</p>'
    )
    assert jmsg[0][1] == ans
    ans = (
        "Storm Prediction Center issues Mesoscale Discussion #1678 "
        "concerning SEVERE POTENTIAL...WATCH UNLIKELY "
        "[watch probability: 20%] "
        "https://www.spc.noaa.gov/products/md/2013/md1678.html"
    )
    assert jmsg[0][0] == ans
    ans = utc(2013, 8, 9, 17, 25)
    assert prod.sts == ans
    ans = utc(2013, 8, 9, 19, 30)
    assert prod.ets == ans

    prod.database_save(dbcursor)
