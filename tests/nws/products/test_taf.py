"""Test TAF Parsing"""

# Third Party
import pytest

# Local
from pyiem.util import get_test_file, utc
from pyiem.nws.products import parser as tafparser


def test_24hour():
    """Test that we can handle a 24 hour value."""
    utcnow = utc(2021, 3, 22, 20, 19)
    prod = tafparser(get_test_file("TAF/TAFGRI.txt"), utcnow=utcnow)
    assert prod.data.valid == utcnow
    assert prod.data.forecasts[0].end_valid == utc(2021, 3, 23)


@pytest.mark.parametrize("database", ["asos"])
def test_dbinsert(dbcursor):
    """Test the database insert."""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFHPN.txt"), utcnow=utcnow)
    prod.sql(dbcursor)


def test_datamodel():
    """Test the resulting datamodel we get"""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFHPN.txt"), utcnow=utcnow)
    assert prod.data.forecasts[6].gust == 20
    assert prod.data.forecasts[5].visibility == 6
    assert prod.data.forecasts[0].presentwx[1] == "VCSH"
    assert prod.data.forecasts[0].sky[0].amount == "OVC"
    assert prod.data.forecasts[0].shear.level == 2000
    assert prod.data.observation.presentwx[0] == "BR"
    assert prod.data.observation.sky[0].amount == "SCT"
    lens = [[0, 2], [1, 1], [2, 2], [3, 1]]
    for pos, _len in lens:
        assert len(prod.data.forecasts[pos].presentwx) == _len


def test_parse():
    """TAF type"""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFJFK.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "OKX issues Terminal Aerodrome Forecast (TAF) "
        "at Jul 25, 13:41 UTC for JFK http://localhost?"
        "pid=201707251341-KOKX-FTUS41-TAFJFK"
    )
    assert j[0][0] == ans
    assert "TAFJFK" in j[0][2]["channels"].split(",")
