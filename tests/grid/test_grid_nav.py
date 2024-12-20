"""Test pyiem.grid.nav"""

from pyiem.grid import nav


def test_api():
    """Test basic things."""
    assert nav.IEMRE.bottom == 23.0


def test_prism_calc():
    """Test that PRISM works out to what we expect."""
    assert (nav.PRISM.right - -66.50) < 0.01
