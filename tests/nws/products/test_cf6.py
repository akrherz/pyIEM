"""Test our CF6 parsing."""
# pylint: disable=redefined-outer-name
import pytest
from pyiem.nws.products.cf6 import parser
from pyiem.util import get_test_file, get_dbconn
from pyiem.reference import TRACE_VALUE


@pytest.fixture
def dbcursor():
    """Return a database cursor."""
    return get_dbconn("iem").cursor()


def test_200302_regex_error():
    """Test failure found with some regex failure."""
    prod = parser(get_test_file("CF6/CF6GRR.txt"))
    assert prod.df.iloc[0]["max"] == 51


def test_200224_time():
    """Test failure found with timestamp parsing."""
    prod = parser(get_test_file("CF6/CF6WYS.txt"))
    assert prod.df.iloc[0]["max"] == 32


def test_basic(dbcursor):
    """Test CF6 Parsing."""
    prod = parser(get_test_file("CF6/CF6DSM.txt"))
    assert prod.df.iloc[0]["max"] == 42
    prod.sql(dbcursor)


def test_trace(dbcursor):
    """Ensure that our decoder is properly dealing with trace values."""
    prod = parser(get_test_file("CF6/CF6SEA.txt"))
    assert prod.df.iloc[15]["wtr"] == TRACE_VALUE
    prod.sql(dbcursor)
