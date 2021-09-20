"""SHEF"""
from pyiem.nws.products.shef import parser
from pyiem.util import utc, get_test_file


def test_a_format():
    """Test the parsing of A format SHEF."""
    utcnow = utc(2021, 9, 17, 12)
    prod = parser(get_test_file("SHEF/A.txt"), utcnow=utcnow)
    assert len(prod.data) == 5
    assert prod.data[0].valid == utc(2021, 9, 10, 11)
    assert prod.data[0].data_created == utc(2021, 9, 17, 16, 40)


def test_b_format():
    """Test the parsing of B format SHEF."""
    utcnow = utc(2021, 9, 17, 0)
    prod = parser(get_test_file("SHEF/B.txt"), utcnow=utcnow)
    assert len(prod.data) == 16
    assert prod.data[0].valid == utc(2021, 9, 16, 21, 45)
    assert prod.data[0].physical_element == "QT"


def test_e_format():
    """Test the parsing of E format SHEF."""
    utcnow = utc(2021, 9, 17, 0)
    prod = parser(get_test_file("SHEF/E.txt"), utcnow=utcnow)
    assert len(prod.data) == 194
    assert prod.data[0].valid == utc(2021, 9, 17)
    assert prod.data[0].data_created == utc(2021, 9, 17)


def test_rtpdtx():
    """Test that we handle the complexity with RTPs."""
    utcnow = utc(2021, 9, 20, 0, 3)
    prod = parser(get_test_file("SHEF/RTPDTX.txt"), utcnow=utcnow)
    assert len(prod.data) == 4 * 22


def test_mixed_AE():
    """Test that we can parse a product with both A and E format included."""
    utcnow = utc(2021, 9, 20, 0, 2)
    prod = parser(get_test_file("SHEF/mixed_AE.txt"), utcnow=utcnow)
    assert len(prod.data) == 79  # unsure this is right, going for now


def test_seconds():
    """Test that we handle DH with seconds provided."""
    utcnow = utc(2021, 9, 20, 0, 3)
    prod = parser(get_test_file("SHEF/RR2LAC.txt"), utcnow=utcnow)
    assert len(prod.data) == 8
    assert prod.data[0].valid == utc(2021, 9, 19, 23, 51, 59)
    assert prod.data[0].str_value == "73"
    assert abs(prod.data[0].num_value - 73.0) < 0.01
