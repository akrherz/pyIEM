"""Test FD."""

import pytest
from pyiem.nws.products.fd import parse_encoding, parser
from pyiem.util import get_test_file, utc


def test_encoding():
    """Test the fun that is this special encoding :/"""
    drct, sknt, tmpc = parse_encoding("790261")
    assert drct == 290
    assert sknt == 102
    assert tmpc == -61


@pytest.mark.parametrize("database", ["asos"])
def test_basic_insert(dbcursor):
    """See that snow_normal goes to the database."""
    utcnow = utc(2023, 3, 8, 2, 1)
    prod = parser(get_test_file("tempwind/FD1US1.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    assert prod.obtime == utcnow.replace(hour=0, minute=0)
    assert prod.ftime == utcnow.replace(hour=6, minute=0)
    dbcursor.execute(
        "SELECT tmpc6000 from alldata_tempwind_aloft where "
        "station = 'KBFF' and obtime = %s and ftime = %s",
        (prod.obtime, prod.ftime),
    )
    row = dbcursor.fetchone()
    assert row["tmpc6000"] is None


def test_ascii_control():
    """Test that aviation ascii chart does not trip us up."""
    utcnow = utc(2023, 3, 9, 1, 59)
    fn = "tempwind/FD1US1_controlchar.txt"
    prod = parser(get_test_file(fn), utcnow=utcnow)
    df = prod.df
    assert len(df.index) == 176
    assert df.at["KFSM", "tmpc9000"] == 4


def test_monthflipping():
    """Test products that span a month bounds."""
    fn = "tempwind/FD1US1_controlchar.txt"
    data = get_test_file(fn)
    utcnow = utc(2023, 2, 28, 1, 59)
    data2 = (
        data.replace("090159", "282220")
        .replace("090000Z", "010000Z")
        .replace("090600Z", "010600Z")
    )
    prod = parser(data2, utcnow=utcnow)
    assert prod.obtime == utc(2023, 3, 1)
    data2 = (
        data.replace("090159", "010220")
        .replace("090000Z", "282300Z")
        .replace("090600Z", "010600Z")
    )
    prod = parser(data2, utcnow=utcnow)
    assert prod.obtime == utc(2023, 2, 28, 23)


def test_valueerror():
    """Test that we get too far of dates apart."""
    utcnow = utc(2023, 2, 19, 1, 59)
    fn = "tempwind/FD1US1_controlchar.txt"
    data = get_test_file(fn).replace("090159", "190159")
    with pytest.raises(ValueError):
        prod = parser(data, utcnow=utcnow)
        print(prod.valid, prod.obtime, prod.ftime)


@pytest.mark.parametrize("database", ["asos"])
def test_truncated(dbcursor):
    """Test that we don't fail on empty prod."""
    utcnow = utc(2023, 3, 8, 2, 1)
    prod = parser(get_test_file("tempwind/FD3CN3.txt")[:100], utcnow=utcnow)
    prod.sql(dbcursor)
    assert prod.df is None


def test_oh_canada():
    """Test that we get the station id right."""
    utcnow = utc(2023, 3, 8, 2, 1)
    prod = parser(get_test_file("tempwind/FD3CN3.txt"), utcnow=utcnow)
    assert prod.df.index.values[0] == "CYVR"


def test_oh_hawaii():
    """Test that we get the station id right."""
    utcnow = utc(2023, 3, 8, 2, 1)
    prod = parser(get_test_file("tempwind/FD0HW9.txt"), utcnow=utcnow)
    assert prod.df.index.values[0] == "PLIH"
