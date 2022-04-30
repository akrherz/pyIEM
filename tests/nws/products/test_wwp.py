"""Can we process the WWP"""

# Third party
import pytest

# Local
from pyiem.nws.products.wwp import parser
from pyiem.util import get_test_file


def test_test_wwp():
    """Test that we can handle test WWP products"""
    prod = parser(get_test_file("WWP/WWP_TEST.txt"))
    assert prod.is_test()


@pytest.mark.parametrize("database", ["postgis"])
def test_wwp9(dbcursor):
    """Test that we can parse this."""
    prod = parser(get_test_file("WWP/WWP9.txt"))
    assert prod.data.num == 159
    assert not prod.data.is_pds
    prod.sql(dbcursor)


@pytest.mark.parametrize("database", ["postgis"])
def test_wwp2006(dbcursor):
    """Test a WWP product from 2006."""
    prod = parser(get_test_file("WWP/WWP_2006.txt"))
    assert prod.data.num == 249
    assert not prod.data.is_pds
    prod.sql(dbcursor)
