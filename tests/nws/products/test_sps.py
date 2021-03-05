"""SPS Parsing"""

import pytest
from pyiem.util import get_test_file
from pyiem.nws.ugc import UGC
from pyiem.nws.products import parser as spsparser


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

    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT count(*) from sps where product_id = %s",
        (prod.get_product_id(),),
    )
    assert dbcursor.fetchall()[0]["count"] > 0
