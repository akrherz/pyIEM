"""Test our CF6 parsing."""
import datetime

import pytest
from pyiem.nws.products.cf6 import parser
from pyiem.util import get_test_file
from pyiem.reference import TRACE_VALUE


@pytest.mark.parametrize("database", ["iem"])
def test_201226_bad_date(dbcursor):
    """Test that no error is emitted for a CF6 with a 'Bad Date'."""
    prod = parser(get_test_file("CF6/CF6WYS_error.txt"))
    prod.sql(dbcursor)
    assert prod


@pytest.mark.parametrize("database", ["iem"])
def test_200421_nan(dbcursor):
    """Test database insert that was failing with NaN values."""
    prod = parser(get_test_file("CF6/CF6MKK.txt"))
    prod.sql(dbcursor)

    dbcursor.execute(
        "SELECT wxcodes from cf6_data_2020 where station = 'PMKK' and "
        "valid = '2020-04-18'"
    )
    assert dbcursor.fetchone()[0] == "X"


def test_200302_regex_error():
    """Test failure found with some regex failure."""
    prod = parser(get_test_file("CF6/CF6GRR.txt"))
    assert prod.df.iloc[0]["max"] == 51


def test_200224_time():
    """Test failure found with timestamp parsing."""
    prod = parser(get_test_file("CF6/CF6WYS.txt"))
    assert prod.df.iloc[0]["max"] == 32


@pytest.mark.parametrize("database", ["iem"])
def test_basic(dbcursor):
    """Test CF6 Parsing."""
    prod = parser(get_test_file("CF6/CF6DSM.txt"))
    assert prod.df.iloc[0]["max"] == 42
    prod.sql(dbcursor)


def test_missing_header():
    """Test exception when there is a missing header."""
    with pytest.raises(ValueError):
        parser(get_test_file("CF6/CF6DSM_bad.txt"))


@pytest.mark.parametrize("database", ["iem"])
def test_nodata(dbcursor):
    """Test when there is no data in the product."""
    prod = parser(get_test_file("CF6/CF6DSM_empty.txt"))
    prod.sql(dbcursor)
    assert prod.df.empty


@pytest.mark.parametrize("database", ["iem"])
def test_trace(dbcursor):
    """Ensure that our decoder is properly dealing with trace values."""
    prod = parser(get_test_file("CF6/CF6SEA.txt"))
    assert prod.df.index.values[0] == datetime.date(2020, 2, 1)
    assert prod.df.iloc[15]["wtr"] == TRACE_VALUE
    prod.sql(dbcursor)

    dbcursor.execute(
        "SELECT possible_sunshine from cf6_data_2020 where station = 'KSEA' "
        "and valid = '2020-02-01'"
    )
    assert dbcursor.fetchone()[0] is None
