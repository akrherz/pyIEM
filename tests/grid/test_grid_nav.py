"""Test pyiem.grid.nav"""

from pyproj import Proj

from pyiem.grid import nav


def test_crs_construction():
    """Test that pyproj is happy with the CRS."""
    for name in nav._GRID_CONFIGS:  # skipcq
        assert Proj(getattr(nav, name).crs)


def test_api():
    """Test basic things."""
    assert nav.IEMRE.bottom == 23.0
    assert nav.IEMRE_CHINA.top == 54.875
    assert nav.IEMRE.affine
    assert nav.IEMRE_EUROPE.affine_image


def test_prism_calc():
    """Test that PRISM works out to what we expect."""
    assert (nav.PRISM4KM.right_edge - -66.4791667) < 0.001
    assert (nav.PRISM.right_edge - nav.PRISM4KM.right_edge) < 0.001


def test_get_nav():
    """Test that we can get a helper."""
    assert nav.get_nav("iemRE")
    assert nav.get_nav("era5LAND", "china")
    assert nav.get_nav("era5LAND", "sa")


def test_get_nav_iemre_sa():
    """Test bug found with bad logic."""
    nav_obj = nav.get_nav("iemre", "sa")
    assert nav_obj.bottom < -40
