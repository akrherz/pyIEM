"""Test TAF Parsing"""

# Third Party
import pytest

from pyiem.nws.products import parser as tafparser
from pyiem.nws.products.taf import parser as real_tafparser
from pyiem.reference import TAF_VIS_OVER_6SM

# Local
from pyiem.util import get_test_file, utc


def test_egrr():
    """Test some cruft."""
    utcnow = utc(1998, 7, 1, 12)
    prod = real_tafparser(get_test_file("TAF/TAF_EGRR.txt"), utcnow=utcnow)
    # Bad PROB30 sections
    assert prod.warnings


def test_taf_amd():
    """Test an old TAF with a variant for a timestamp."""
    utcnow = utc(1999, 1, 1, 2)
    prod = real_tafparser(get_test_file("TAF/TAF_amd.txt"), utcnow=utcnow)
    assert not prod.warnings
    assert len(prod.data[0].forecasts) == 4


def test_taf_collective():
    """Test that we can process a legacy TAF collective :/"""
    utcnow = utc(2000, 4, 6, 20)
    prod = real_tafparser(
        get_test_file("TAF/TAF_collective.txt"), utcnow=utcnow
    )
    assert prod.data[0].forecasts[0].valid == utc(2000, 4, 6, 19)
    assert prod.data[0].forecasts[1].valid == utc(2000, 4, 7, 4)
    assert prod.data[0].forecasts[3].valid == utc(2000, 4, 7, 9)


def test_250926_taflan_badfinal():
    """Test the parsing with the file FEW being cut off."""
    utcnow = utc(2025, 9, 26, 18)
    prod = real_tafparser(get_test_file("TAF/TAFLAN.txt"), utcnow=utcnow)
    assert prod.data[0].forecasts[-1].sky[0].amount == "FEW"
    assert prod.data[0].forecasts[-1].sky[0].level == 4_000


def test_250818_tafags():
    """Test a TAF found in 2008 that fails."""
    utcnow = utc(2008, 1, 1, 6)
    prod = real_tafparser(get_test_file("TAF/TAFAGS.txt"), utcnow=utcnow)
    assert not prod.warnings
    assert len(prod.data[0].forecasts) == 4


def test_250818_tafags_2():
    """Test a TAF found in 2008 that fails."""
    utcnow = utc(2008, 1, 1, 6)
    prod = real_tafparser(get_test_file("TAF/TAFAGS_2.txt"), utcnow=utcnow)
    assert len(prod.data[0].forecasts) == 5


def test_250818_taftop():
    """Test something found in the wild."""
    utcnow = utc(2025, 8, 18, 12)
    prod = real_tafparser(get_test_file("TAF/TAFTOP.txt"), utcnow=utcnow)
    assert len(prod.data[0].forecasts) == 3


def test_250812_tafgrr():
    """Test that the PROB gets properly parsed here."""
    utcnow = utc(2025, 8, 12, 18)
    prod = real_tafparser(get_test_file("TAF/TAFGRR.txt"), utcnow=utcnow)
    ans = "1219/1318 23009KT P6SM VCTS SCT040CB"
    taf = prod.data[0]
    assert taf.observation.raw == ans
    assert taf.forecasts[0].visibility == 2
    assert len(taf.forecasts) == 6
    ans = "TEMPO 1219/1221 2SM TSRA BKN040CB"
    assert taf.forecasts[0].raw == ans


def test_tafjxn():
    """Test that we get the prob in this TAF."""
    utcnow = utc(2025, 8, 4, 0)
    prod = real_tafparser(get_test_file("TAF/TAFJXN.txt"), utcnow=utcnow)
    assert prod.data[0].forecasts
    ans = "0318/0418 29013G21KT P6SM BKN025"
    assert prod.data[0].observation.raw == ans


def test_tafpam():
    """Test what was likely a mis-fire."""
    utcnow = utc(2025, 8, 7, 0)
    prod = real_tafparser(get_test_file("TAF/TAFPAM.txt"), utcnow=utcnow)
    taf = prod.data[0]
    assert taf.observation.ftype == 0
    assert taf.forecasts[0].ftype == 2
    assert taf.forecasts[1].ftype == 5


def test_gh1104_tafhky():
    """Test that we deal with PROB30."""
    utcnow = utc(2025, 8, 15, 0)
    prod = real_tafparser(get_test_file("TAF/TAFHKY.txt"), utcnow=utcnow)
    assert prod.data[0].observation.ftype == 0
    answers = [2, 1, 1, 3, 1]
    for idx in range(5):
        assert prod.data[0].forecasts[idx].ftype == answers[idx]
    assert prod.data[0].forecasts[3].visibility == 4


@pytest.mark.parametrize("database", ["asos"])
def test_gh453_skc(dbcursor):
    """Test that SKC gets encoded as clear and not present weather."""
    utcnow = utc(2024, 3, 26, 6)
    prod = real_tafparser(get_test_file("TAF/TAFOLF.txt"), utcnow=utcnow)
    assert prod.data[0].observation.presentwx == []
    assert prod.data[0].observation.sky[0].amount == "SKC"
    assert prod.data[0].observation.sky[0].level is None
    prod.sql(dbcursor)


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
    assert prod.data[0].observation.visibility == 6


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
    taf = prod.data[0]
    assert taf.observation.valid == utc(2017, 7, 25, 13, 41)
    assert taf.forecasts[0].valid == utc(2017, 7, 25, 16)
    assert taf.forecasts[1].valid == utc(2017, 7, 25, 22)
    assert taf.forecasts[2].valid == utc(2017, 7, 26, 5)
    assert taf.forecasts[3].valid == utc(2017, 7, 26, 14)
    assert taf.forecasts[4].valid == utc(2017, 7, 26, 17)


def test_jan1():
    """Test when TAF crosses 1 Jan."""
    utcnow = utc(2020, 12, 31, 17, 21)
    prod = tafparser(get_test_file("TAF/TAFDSM.txt"), utcnow=utcnow)
    assert prod.data[0].forecasts[2].valid == utc(2021, 1, 1, 9)


def test_feb29():
    """Test when TAF crosses 1 Jan."""
    utcnow = utc(2020, 3, 1, 0, 5)
    prod = tafparser(get_test_file("TAF/TAFDSM_2.txt"), utcnow=utcnow)
    assert prod.data[0].observation.valid == utc(2020, 2, 29, 23, 54)


def test_24hour():
    """Test that we can handle a 24 hour value."""
    utcnow = utc(2021, 3, 22, 20, 19)
    prod = tafparser(get_test_file("TAF/TAFGRI.txt"), utcnow=utcnow)
    assert prod.data[0].valid == utcnow
    assert prod.data[0].forecasts[0].end_valid == utc(2021, 3, 23)


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
    tafparser(text.replace("2011/2012", "Q011/Q012"), utcnow=utcnow)


def test_datamodel():
    """Test the resulting datamodel we get"""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFHPN.txt"), utcnow=utcnow)
    taf = prod.data[0]
    assert taf.forecasts[6].gust == 20
    assert taf.forecasts[5].visibility == TAF_VIS_OVER_6SM
    assert taf.forecasts[0].presentwx[1] == "VCSH"
    assert taf.forecasts[0].sky[0].amount == "OVC"
    assert taf.forecasts[0].shear.level == 2000
    assert taf.observation.presentwx[0] == "BR"
    assert taf.observation.sky[0].amount == "SCT"
    lens = [[0, 2], [1, 1], [2, 2], [3, 1]]
    for pos, _len in lens:
        assert len(taf.forecasts[pos].presentwx) == _len


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
