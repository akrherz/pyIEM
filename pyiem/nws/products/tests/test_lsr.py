"""Test Local Storm Report parsing."""

from pyiem.util import get_test_file
from pyiem.nws.products.lsr import parser


def test_issue61_future():
    """Can we properly warn on a product from the future."""
    prod = parser(get_test_file('LSR/LSRGSP_future.txt'))
    assert len(prod.warnings) == 1
    assert not prod.lsrs
