"""Test TAF Parsing"""

from pyiem.util import get_test_file, utc
from pyiem.nws.products.taf import parser as tafparser


def test_parse():
    """TAF type"""
    utcnow = utc(2017, 7, 25)
    prod = tafparser(get_test_file("TAF/TAFJFK.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "OKX issues Terminal Aerodrome Forecast (TAF) "
        "at Jul 25, 13:41 UTC for JFK http://localhost?"
        "pid=201707251341-KOKX-FTUS41-TAFJFK")
    assert j[0][0] == ans
    assert "TAFJFK" in j[0][2]['channels'].split(",")
