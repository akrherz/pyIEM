"""Test our CF6 parsing."""

import datetime

import pytest

from pyiem.nws.products.cf6 import parser
from pyiem.reference import TRACE_VALUE
from pyiem.util import get_test_file, utc


def test_240503_future_again():
    """Test that anything from today/future that is Null is not included."""
    utcnow = utc(2024, 5, 3, 11, 59)
    prod = parser(get_test_file("CF6/CF6FYV_future.txt"), utcnow=utcnow)
    assert len(prod.df.index) == 2


def test_230628_future():
    """Test the exclusion of data from the future!"""
    # Data from the 27th is taken as it is tricky to get this perfect
    utcnow = utc(2023, 6, 26, 16, 26)
    prod = parser(get_test_file("CF6/CF6ANC.txt"), utcnow=utcnow)
    assert prod.warnings
    assert len(prod.df.index) == 25


@pytest.mark.parametrize("database", ["iem"])
def test_220707_nofloat(dbcursor):
    """Ensure that wxcodes goes to the database verbatim."""
    prod = parser(get_test_file("CF6/CF6DSM.txt"))
    assert len(prod.df.index) == 22
    assert prod.df.iloc[0]["wx"] == "1"
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT wxcodes from cf6_data_2020 where station = 'KDSM' and "
        "valid = '2020-02-01'"
    )
    assert dbcursor.fetchone()["wxcodes"] == "1"
    dbcursor.execute(
        "SELECT wxcodes from cf6_data_2020 where station = 'KDSM' and "
        "valid = '2020-02-02'"
    )
    assert dbcursor.fetchone()["wxcodes"] is None


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
    assert dbcursor.fetchone()["wxcodes"] == "X"


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
    assert dbcursor.fetchone()["possible_sunshine"] is None
