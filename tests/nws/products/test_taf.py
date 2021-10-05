"""Test TAF Parsing"""

# Third Party
import pytest

# Local
from pyiem.util import get_test_file, utc
from pyiem.reference import TAF_VIS_OVER_6SM
from pyiem.nws.products import parser as tafparser
from pyiem.nws.products.taf import parser as real_tafparser


def test_210525_badtimestamp():
    """Test that we do not error out with this product."""
    utcnow = utc(2021, 5, 25, 16)
    with pytest.raises(ValueError) as exp:
        real_tafparser(get_test_file("TAF/TAFLBF.txt"), utcnow=utcnow)
    assert str(exp.value) == "Found invalid hr: 63 from '256300'"


def test_210428_issue449():
    """Test that we differentiate 6 vs 6+ mile visibility."""
    data = get_test_file("TAF/TAFDSM_2.txt").replace(
        " P6SM OVC008", " 6SM OVC008"
    )
    prod = tafparser(data, utcnow=utc(2000))
    assert prod.data.observation.visibility == 6


def test_210328_badtaf():
    """Test that we gracefully handle an invalid TAF found in the wild."""
    utcnow = utc(2021, 3, 28, 16)
    prod = real_tafparser(get_test_file("TAF/TAFTPP.txt"), utcnow=utcnow)
    j = prod.get_jabbers("")
    assert j


def test_210323_timestamps():
    """Test that our timestamps generated are right, sigh."""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFJFK.txt"), utcnow=utcnow)
    assert prod.data.observation.valid == utc(2017, 7, 25, 13, 41)
    assert prod.data.forecasts[0].valid == utc(2017, 7, 25, 16)
    assert prod.data.forecasts[1].valid == utc(2017, 7, 25, 22)
    assert prod.data.forecasts[2].valid == utc(2017, 7, 26, 5)
    assert prod.data.forecasts[3].valid == utc(2017, 7, 26, 14)
    assert prod.data.forecasts[4].valid == utc(2017, 7, 26, 17)


def test_jan1():
    """Test when TAF crosses 1 Jan."""
    utcnow = utc(2020, 12, 31, 17, 21)
    prod = tafparser(get_test_file("TAF/TAFDSM.txt"), utcnow=utcnow)
    assert prod.data.forecasts[2].valid == utc(2021, 1, 1, 9)


def test_feb29():
    """Test when TAF crosses 1 Jan."""
    utcnow = utc(2020, 3, 1, 0, 5)
    prod = tafparser(get_test_file("TAF/TAFDSM_2.txt"), utcnow=utcnow)
    assert prod.data.observation.valid == utc(2020, 2, 29, 23, 54)


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
    text = get_test_file("TAF/TAFHPN.txt")
    prod = tafparser(text, utcnow=utcnow)
    prod.sql(dbcursor)
    # Do it again so to test deletion
    prod = tafparser(text.replace("200931 AAS", "200932 AAS"), utcnow=utcnow)
    prod.sql(dbcursor)
    # bad TEMPO
    prod = tafparser(text.replace("2011/2012", "Q011/Q012"), utcnow=utcnow)


def test_datamodel():
    """Test the resulting datamodel we get"""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFHPN.txt"), utcnow=utcnow)
    assert prod.data.forecasts[6].gust == 20
    assert prod.data.forecasts[5].visibility == TAF_VIS_OVER_6SM
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
        "pid=201707251341-KOKX-FTUS41-TAFJFK-AAA"
    )
    assert j[0][0] == ans
    assert "TAFJFK" in j[0][2]["channels"].split(",")
    ans = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/219/"
        "station:KJFK::valid:2017-07-25%201341.png"
    )
    assert j[0][2]["twitter_media"] == ans
