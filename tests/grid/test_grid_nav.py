"""Test pyiem.grid.nav"""

from pyiem.grid import nav


def test_api():
    """Test basic things."""
    assert nav.IEMRE.bottom == 23.0
    assert nav.IEMRE_CHINA.top == 54.875
    assert nav.IEMRE.affine
    assert nav.IEMRE_EUROPE.affine_image


def test_prism_calc():
    """Test that PRISM works out to what we expect."""
    assert (nav.PRISM.right - -66.50) < 0.01


def test_get_nav():
    """Test that we can get a helper."""
    assert nav.get_nav("iemRE", "")
    assert nav.get_nav("era5LAND", "china")
