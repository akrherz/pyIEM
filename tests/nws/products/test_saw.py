"""Can we process the SAW"""

import pytest
from pyiem.nws.products.saw import parser as sawparser
from pyiem.util import utc, get_test_file


@pytest.mark.parametrize("database", ["postgis"])
def test_220308_jan1_saw(dbcursor):
    """Test that expiration time we get for these SAWs."""
    utcnow = utc(2022, 1, 1, 16, 48)
    prod = sawparser(get_test_file("SAW/SAW3_jan1.txt"), utcnow=utcnow)
    assert prod.ets == utc(2022, 1, 2, 0, 0)
    prod.sql(dbcursor)
    dbcursor.execute(
        "select expired from watches where num = 3 and "
        "extract(year from expired) = 2022"
    )
    assert dbcursor.fetchone()[0] == utc(2022, 1, 2, 0, 0)

    utcnow = utc(2022, 1, 2, 0, 3)
    prod = sawparser(get_test_file("SAW/SAW3_jan1_can.txt"), utcnow=utcnow)
    assert prod.valid == utcnow
    prod.sql(dbcursor)
    dbcursor.execute(
        "select expired from watches where num = 3 and "
        "extract(year from expired) = 2022"
    )
    assert dbcursor.fetchone()[0] == utcnow


def test_181231_linkisok():
    """The plain text tweet should have a space."""
    utcnow = utc(2014, 3, 10, 3, 29)
    utcnow = utcnow.replace(microsecond=100)
    prod = sawparser(get_test_file("SAW/SAW3.txt"), utcnow=utcnow)
    assert prod.ets.microsecond == 0
    jmsgs = prod.get_jabbers("")
    ans = (
        "SPC issues Severe Thunderstorm Watch 503 till 9:00Z "
        "https://www.spc.noaa.gov/products/watch/2014/ww0503.html"
    )
    assert jmsgs[0][0] == ans
    assert jmsgs[0][2]["channels"] == "SPC,SPC.SVRWATCH"


@pytest.mark.parametrize("database", ["postgis"])
def test_replacement(dbcursor):
    """Can we do replacements?"""
    utcnow = utc(2017, 8, 21, 9, 17)
    prod = sawparser(get_test_file("SAW/SAW-replaces.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    jmsgs = prod.get_jabbers("")
    assert len(jmsgs) == 1
    ans = (
        "SPC issues Severe Thunderstorm Watch"
        " 153 till 17:00Z, new watch replaces WW 1 "
        "https://www.spc.noaa.gov/products/watch/2017/ww0153.html"
    )
    assert jmsgs[0][0] == ans
    assert "twitter" in jmsgs[0][2]


def test_saw3():
    """SAW3"""
    utcnow = utc(2014, 3, 10, 3, 29)
    sts = utcnow.replace(hour=3, minute=35)
    ets = utcnow.replace(hour=9, minute=0)
    prod = sawparser(get_test_file("SAW/SAW3.txt"), utcnow=utcnow)
    assert prod.saw == 3
    assert abs(prod.geometry.area - 7.73) < 0.01
    assert prod.ww_num == 503
    assert prod.sts == sts
    assert prod.ets == ets
    assert prod.ww_type == prod.SEVERE_THUNDERSTORM
    assert prod.action == prod.ISSUES


@pytest.mark.parametrize("database", ["postgis"])
def test_cancelled(dbcursor):
    """SAW-cancelled make sure we can cancel a watch"""
    utcnow = utc(2014, 3, 10, 3, 29)
    prod = sawparser(get_test_file("SAW/SAW-cancelled.txt"), utcnow=utcnow)
    assert prod.action == prod.CANCELS
    j = prod.get_jabbers(None)
    ans = (
        "Storm Prediction Center cancels Weather Watch Number 575 "
        "https://www.spc.noaa.gov/products/watch/2014/ww0575.html"
    )
    assert j[0][0] == ans
    prod.sql(dbcursor)
    prod.compute_wfos(dbcursor)
