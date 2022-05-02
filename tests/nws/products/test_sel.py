"""Can we process the WWP"""

# Third party
import pytest

# Local
from pyiem.nws.products import parser
from pyiem.util import get_test_file


def test_sel():
    """Test that we can handle test WWP products"""
    prod = parser(get_test_file("SEL/SEL9.txt"))
    assert not prod.is_test()


@pytest.mark.parametrize("database", ["postgis"])
def test_sel5_2007(dbcursor):
    """Test that we can parse this."""
    prod = parser(get_test_file("SEL/SEL5_2007.txt"))
    assert prod.data.num == 205
    prod.sql(dbcursor)
