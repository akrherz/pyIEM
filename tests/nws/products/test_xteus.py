"""Can we process the XTEUS"""

import pytest

# Local
from pyiem.nws.products.xteus import parser
from pyiem.util import get_test_file, utc


def test_221228_duplicated_location():
    """Test that we can make assumptions about this duplicated location."""
    data = get_test_file("XTEUS/XTEUS_double.txt")
    utcnow = utc(2015, 3, 29, 18, 38)
    prod = parser(data, utcnow=utcnow)
    assert prod.warnings
    df = prod.data[prod.data["name"] == "Big Black River"]
    assert df.iloc[0]["value"] == -9


@pytest.mark.parametrize("database", ["iem"])
def test_nowrite(dbcursor):
    """Test database insert."""
    data = get_test_file("XTEUS/XTEUS.txt")
    utcnow = utc(2022, 12, 28, 0, 41)
    prod = parser(data, utcnow=utcnow)
    prod.sql(dbcursor)
    # Modify to make it slightly older
    prod = parser(data.replace("280041", "280040"), utcnow=utcnow)
    prod.sql(dbcursor)
    # Modify to make it slightly newer
    prod = parser(data.replace("280041", "280042"), utcnow=utcnow)
    prod.sql(dbcursor)


def test_value_error():
    """Test that we get a ValueError when the product has no xml."""
    data = get_test_file("XTEUS/XTEUS_first.txt").replace("dwml", "")
    with pytest.raises(ValueError):
        parser(data)


def test_first():
    """Test the first XTEUS we have in the archive"""
    prod = parser(get_test_file("XTEUS/XTEUS_first.txt"))
    assert len(prod.data.index) == 2


def test_test_wwp():
    """Test that we can handle products"""
    prod = parser(get_test_file("XTEUS/XTEUS.txt"))
    assert len(prod.data.index) == 4


@pytest.mark.parametrize("database", ["iem"])
def test_sql(dbcursor):
    """Test database insert."""
    prod = parser(get_test_file("XTEUS/XTEUS.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT count(*) from wpc_national_high_low where date = '2022-12-27'"
    )
    assert dbcursor.fetchone()["count"] == 4
