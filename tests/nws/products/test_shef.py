"""SHEF"""
from pyiem.nws.products.shef import parser
from pyiem.util import utc, get_test_file


def test_a_format():
    """Test the parsing of A format SHEF."""
    utcnow = utc(2021, 9, 17, 12)
    prod = parser(get_test_file("SHEF/A.txt"), utcnow=utcnow)
    assert len(prod.data) == 6
    assert prod.data[0].valid == utc(2021, 9, 10, 11)


def test_b_format():
    """Test the parsing of B format SHEF."""
    utcnow = utc(2021, 9, 17, 0)
    prod = parser(get_test_file("SHEF/B.txt"), utcnow=utcnow)
    assert len(prod.data) == 16
    # assert prod.data[0].valid == utc(2021, 9, 16, 21, 45)


def test_e_format():
    """Test the parsing of E format SHEF."""
    utcnow = utc(2021, 9, 17, 0)
    prod = parser(get_test_file("SHEF/E.txt"), utcnow=utcnow)
    assert len(prod.data) == 194
    assert prod.data[0].valid == utc(2021, 9, 17)
