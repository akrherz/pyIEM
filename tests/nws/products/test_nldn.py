"""Test NLDN."""

import pytest
from pyiem.nws.products.nldn import parser
from pyiem.util import get_test_file, get_dbconn


@pytest.fixture
def cursor():
    """Return a database cursor."""
    return get_dbconn("nldn").cursor()


def test_1_basic():
    """CLIBNA is a new diction"""
    np = parser(get_test_file("NLDN/example.bin", fponly=True))
    assert len(np.df.index) == 50


def test_sql(cursor):
    """Test that we can insert data."""
    np = parser(get_test_file("NLDN/example.bin", fponly=True))
    np.sql(cursor)
