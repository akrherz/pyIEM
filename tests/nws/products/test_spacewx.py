"""Can we process the spacewx"""

from pyiem.nws.products.spacewx import parser
from pyiem.util import utc, get_test_file


def test_spacewx():
    """See if we can parse a space weather product"""
    utcnow = utc(2014, 5, 10)
    prod = parser(get_test_file("SPACEWX.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost/")
    ans = (
        "Space Weather Prediction Center issues "
        "CANCEL WATCH: Geomagnetic Storm Category G3 Predicted "
        "http://localhost/?pid=201405101416-KWNP-WOXX22-WATA50"
    )
    assert j[0][0] == ans
