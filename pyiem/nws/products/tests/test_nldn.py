"""Test NLDN."""

from pyiem.nws.products.nldn import parser
from pyiem.util import get_test_file


def test_1_basic():
    """CLIBNA is a new diction"""
    np = parser(get_test_file('NLDN/example.bin', fponly=True))
    assert len(np.df.index) == 50
