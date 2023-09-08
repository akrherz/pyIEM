"""Can we process the WWP"""

# Third party
import pytest

# Local
from pyiem.nws.products import parser
from pyiem.util import get_test_file


@pytest.mark.parametrize("database", ["postgis"])
def test_can(dbcursor):
    """Test database updates for a cancels SEL."""
    prod = parser(get_test_file("SEL/SEL_CAN.txt"))
    assert prod.data.num == 5700
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT * from watches where num = 5700 "
        "and extract(year from issued) = 2015"
    )
    assert dbcursor.rowcount == 0


@pytest.mark.parametrize("database", ["postgis"])
def test_sel(dbcursor):
    """Test that we can handle test WWP products"""
    prod = parser(get_test_file("SEL/SEL9.txt"))
    assert not prod.is_test()
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT product_id_sel from watches where num = 169 "
        "and extract(year from issued) = 2022"
    )
    assert dbcursor.fetchone()["product_id_sel"] == prod.get_product_id()


@pytest.mark.parametrize("database", ["postgis"])
def test_sel5_2007(dbcursor):
    """Test that we can parse this."""
    prod = parser(get_test_file("SEL/SEL5_2007.txt"))
    assert prod.data.num == 205
    prod.sql(dbcursor)
