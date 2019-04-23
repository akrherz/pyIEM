"""Test MOS Parsing."""

import pytest
from pyiem.nws.products.mos import parser as mosparser
from pyiem.util import get_dbconn, utc, get_test_file


@pytest.fixture
def cursor():
    """Return a database cursor."""
    return get_dbconn('mos').cursor()


def test_180125_empty(cursor):
    """Can we parse a MOS product with empty data"""
    utcnow = utc(2018, 1, 26, 1)
    prod = mosparser(get_test_file("MOS/MET_empty.txt"), utcnow=utcnow)
    assert len(prod.data) == 3
    assert len(prod.data[0]['data'].keys()) == 21

    inserts = prod.sql(cursor)
    assert inserts == 42


def test_parse(cursor):
    """MOS type"""
    utcnow = utc(2017, 8, 12, 12)
    prod = mosparser(get_test_file("MOS/METNC1.txt"), utcnow=utcnow)
    assert len(prod.data) == 4
    assert len(prod.data[0]['data'].keys()) == 21

    inserts = prod.sql(cursor)
    assert inserts == (4 * 21)


def test_empty_nbm(cursor):
    """Does an empty product trip us up."""
    utcnow = utc(2018, 11, 7, 17)
    prod = mosparser(get_test_file("MOS/NBSUSA_empty.txt"), utcnow=utcnow)
    assert len(prod.data) == 2

    inserts = prod.sql(cursor)
    assert inserts == 0


def test_nbm(cursor):
    """Can we parse the NBM data."""
    utcnow = utc(2018, 11, 7, 15)
    prod = mosparser(get_test_file("MOS/NBSUSA.txt"), utcnow=utcnow)
    assert len(prod.data) == 2

    inserts = prod.sql(cursor)
    assert inserts == (2 * 21)

    cursor.execute("""
        SELECT count(*), max(ftime) from t2018
        where model = 'NBS' and station = 'KALM' and runtime = %s
    """, (utcnow, ))
    row = cursor.fetchone()
    assert row[0] == 21
    assert row[1] == utc(2018, 11, 10, 9)
