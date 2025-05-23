"""Test pyiem.wmo module."""

from pyiem.util import get_test_file
from pyiem.wmo import WMOProduct


def test_nullbyte():
    """Test the removal of a product that has a null byte."""
    prod = WMOProduct(get_test_file("METAR/nullbyte.txt"))
    assert "\x00" not in prod.unixtext
