"""SPS Parsing"""

import pytest
from pyiem.reference import TWEET_CHARS
from pyiem.util import get_test_file, utc
from pyiem.nws.ugc import UGC
from pyiem.nws.products import parser as spsparser


@pytest.mark.parametrize("database", ["postgis"])
def test_issue399_multisegment(dbcursor):
    """Test that inserts are made for multi-segment products."""
    prod = spsparser(get_test_file("SPS/SPSRIW.txt"))
    prod.sql(dbcursor)
    ugcs = [["WYZ020", "WYZ022"], ["WYZ009", "WYZ010", "WYZ011"]]
    for segnum, ans in enumerate(ugcs):
        dbcursor.execute(
            "SELECT ugcs from sps where product_id = %s and segmentnum = %s",
            (prod.get_product_id(), segnum),
        )
        assert dbcursor.fetchone()[0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_210314_sps_without_polygon(dbcursor):
    """Test that we insert a record for a SPS without a polygon."""
    prod = spsparser(get_test_file("SPS/SPSOKX.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT expire from sps where product_id = %s and ST_isempty(geom)",
        (prod.get_product_id(),),
    )
    assert dbcursor.fetchone()[0] == utc(2021, 3, 15, 8)


def test_issue393_tweet_length():
    """Test that we actually truncate messages."""
    longname = "HERE THERE EVERYWHERE, SUCH A LONG NAME..."
    ugp = {
        "OHZ066": UGC("OH", "Z", "066", name=longname),
        "OHZ067": UGC("OH", "Z", "067", name=longname),
        "WVZ008": UGC("WV", "Z", "008", name=longname),
        "WVZ016": UGC("WV", "Z", "016", name=longname),
        "WVZ040": UGC("WV", "Z", "040", name=longname),
    }
    prod = spsparser(get_test_file("SPS/SPSRLX.txt"), ugc_provider=ugp)
    j = prod.get_jabbers("")
    meat = j[0][2]["twitter"].rsplit(" ", 1)[0]
    assert (len(meat) + 24) < TWEET_CHARS


@pytest.mark.parametrize("database", ["postgis"])
def test_sps_ibw1(dbcursor):
    """Test parsing of 2021 IBW tags."""
    prod = spsparser(get_test_file("SPS/SPSBMX_IBW1.txt"))
    prod.sql(dbcursor)
    assert not prod.warnings
    assert prod.segments[0].windtag == "40"
    assert prod.segments[0].hailtag == "0.88"
    assert prod.segments[0].landspouttag == "POSSIBLE"
    assert prod.segments[0].waterspouttag is None
    res = prod.get_jabbers("")
    assert res[0][0].find("landspout: POSSIBLE") > 0


def test_sps_ibw2():
    """Test the jabber message generated."""
    prod = spsparser(get_test_file("SPS/SPSBMX_IBW2.txt"))
    j = prod.get_jabbers("")
    ans = (
        "BMX issues SIGNIFICANT WEATHER ADVISORY FOR SOUTHWESTERN MARENGO "
        "COUNTY UNTIL 515 PM CDT [waterspout: OBSERVED, wind: &lt;30 MPH, "
        "hail: 0.00 IN]  for ((ALZ039)) [AL] "
        "?pid=201805292152-KBMX-WWUS84-SPSBMX"
    )
    assert j[0][0] == ans
    assert "twitter_media" in j[0][2]


@pytest.mark.parametrize("database", ["postgis"])
def test_sps_ibw3(dbcursor):
    """Text the database save of this SPS."""
    prod = spsparser(get_test_file("SPS/SPSBMX_IBW3.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT tml_valid, tml_sknt, tml_geom, tml_geom_line, ugcs "
        "from sps where product_id = %s",
        (prod.get_product_id(),),
    )
    row = dbcursor.fetchone()
    assert row[0] is not None
    assert row[1] == 23
    assert row[2] is not None
    assert row[3] is None
    assert len(row[4]) == 2


@pytest.mark.parametrize("database", ["postgis"])
def test_sps(dbcursor):
    """Can we parse a SPS properly, yes we can!"""
    up = {"ALZ039": UGC("AL", "Z", "039", name="Marengo")}
    prod = spsparser(get_test_file("SPS/SPSBMX.txt"), ugc_provider=up)
    jmsgs = prod.get_jabbers("http://localhost")
    assert len(prod.segments) == 2
    assert len(jmsgs) == 1
    expected = (
        "<p>BMX issues <a href='http://localhost?pid=201805292152-"
        "KBMX-WWUS84-SPSBMX'>SIGNIFICANT WEATHER ADVISORY FOR "
        "SOUTHWESTERN MARENGO COUNTY UNTIL 515 PM CDT</a></p>"
    )
    assert jmsgs[0][1] == expected
    assert "SPSBMX" in jmsgs[0][2]["channels"]
    assert "SPS..." in jmsgs[0][2]["channels"]
    assert "SPSBMX.ALZ039" in jmsgs[0][2]["channels"]
    assert "ALZ039" in jmsgs[0][2]["channels"]
    assert "SPS.AL" in jmsgs[0][2]["channels"]

    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT count(*) from sps where product_id = %s",
        (prod.get_product_id(),),
    )
    assert dbcursor.fetchall()[0]["count"] > 0
