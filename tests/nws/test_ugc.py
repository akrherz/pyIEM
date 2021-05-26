"""Can we parse UGC strings"""

import pytest
from pyiem.exceptions import UGCParseException
from pyiem.util import utc
from pyiem.nws import ugc

STR1 = "DCZ001-170200-"
STR2 = "DCZ001-MDZ004>007-009>011-013-014-016>018-VAZ036>042-050>057-170200-"


def test_missed_ugc():
    """Invalid encoded county string, check that NMC006 was not included"""
    text = (
        "NMC001-005>007-011-019-027-028-031-033-039-041-043-045-"
        "047-049-053-055-057-061-040300-"
    )
    valid = utc(2018, 6, 4, 3, 0)
    (ugcs, expire) = ugc.parse(text, valid)
    assert expire == valid
    assert ugcs[3] != ugc.UGC("NM", "C", "006")


def test_louisana():
    """Test that some specific logic works."""
    ugcs = [ugc.UGC("LA", "C", i) for i in range(100)]
    res = ugc.ugcs_to_text(ugcs)
    ans = "100 parishes in [LA]"
    assert res == ans


def test_totextstr():
    """See if we can generate a proper string from a UGCS"""
    ugcs = [
        ugc.UGC("DC", "Z", "001"),
        ugc.UGC("IA", "C", "001"),
        ugc.UGC("IA", "C", "002"),
    ]
    assert (
        ugc.ugcs_to_text(ugcs)
        == "((DCZ001)) [DC] and ((IAC001)), ((IAC002)) [IA]"
    )


def test_parse_exception():
    """Test that we raise a proper exception when given bad data."""
    valid = utc(2008, 12, 17, 3, 0)
    text = "IA078-170300-"
    with pytest.raises(UGCParseException):
        ugc.parse(text, valid)


def test_str1():
    """check ugc.parse of STR1 parsing"""
    valid = utc(2008, 12, 17, 3, 0)
    (ugcs, expire) = ugc.parse(STR1, valid)

    expire_answer = valid.replace(hour=2)
    ugcs_answer = [ugc.UGC("DC", "Z", "001")]

    assert ugcs == ugcs_answer
    assert expire == expire_answer


def test_str2():
    """check ugc.parse of STR2 parsing"""
    valid = utc(2008, 12, 17, 3, 0)
    (ugcs, expire) = ugc.parse(STR2, valid)

    expire_answer = valid.replace(hour=2)
    ugcs_answer = [
        ugc.UGC("DC", "Z", "001"),
        ugc.UGC("MD", "Z", "004"),
        ugc.UGC("MD", "Z", "005"),
        ugc.UGC("MD", "Z", "006"),
        ugc.UGC("MD", "Z", "007"),
        ugc.UGC("MD", "Z", "009"),
        ugc.UGC("MD", "Z", "010"),
        ugc.UGC("MD", "Z", "011"),
        ugc.UGC("MD", "Z", "013"),
        ugc.UGC("MD", "Z", "014"),
        ugc.UGC("MD", "Z", "016"),
        ugc.UGC("MD", "Z", "017"),
        ugc.UGC("MD", "Z", "018"),
        ugc.UGC("VA", "Z", "036"),
        ugc.UGC("VA", "Z", "037"),
        ugc.UGC("VA", "Z", "038"),
        ugc.UGC("VA", "Z", "039"),
        ugc.UGC("VA", "Z", "040"),
        ugc.UGC("VA", "Z", "041"),
        ugc.UGC("VA", "Z", "042"),
        ugc.UGC("VA", "Z", "050"),
        ugc.UGC("VA", "Z", "051"),
        ugc.UGC("VA", "Z", "052"),
        ugc.UGC("VA", "Z", "053"),
        ugc.UGC("VA", "Z", "054"),
        ugc.UGC("VA", "Z", "055"),
        ugc.UGC("VA", "Z", "056"),
        ugc.UGC("VA", "Z", "057"),
    ]

    assert ugcs == ugcs_answer
    assert expire == expire_answer
