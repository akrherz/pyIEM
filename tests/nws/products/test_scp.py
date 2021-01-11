"""Can we process the SCP"""

import pytest
from pyiem.nws.products.scp import parser
from pyiem.util import utc, get_test_file


@pytest.mark.parametrize("database", ["asos"])
def test_201026(dbcursor):
    """Basic test."""
    utcnow = utc(2020, 10, 26, 15, 5)
    prod = parser(get_test_file("NESDIS/SCPPR2.txt"), utcnow=utcnow)
    assert len(prod.data) == 8
    inserts = prod.sql(dbcursor)
    assert inserts == 8


def test_jan1():
    """Test that we get a product crossing a year right."""
    utcnow = utc(2020, 1, 1, 0, 30)
    prod = parser(get_test_file("NESDIS/SCPCR1_jan1.txt"), utcnow=utcnow)
    assert prod.data[0].valid == utc(2019, 12, 31, 23, 57)
