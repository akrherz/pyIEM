"""Test HWO parsing."""

from pyiem.nws.products.hwo import parser
from pyiem.util import get_test_file


def test_nostorms():
    """Test the channel emitted when there is no storms forecast."""
    prod = parser(get_test_file("HWO/HWODMX_nowx.txt"))
    j = prod.get_jabbers("")
    assert j[0][2]["channels"].split(",")[0] == "HWODMX.NONE"
