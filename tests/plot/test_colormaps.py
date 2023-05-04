"""test our colormaps.py"""
from pyiem.plot.colormaps import dep_erosion, get_cmap, nwsprecip, stretch_cmap


def test_get_cmap():
    """Test we can call our get_cmap proxy."""
    cmap = get_cmap("jet")
    assert cmap is not None
    assert nwsprecip() is not None


def test_stretch():
    """can we do what we hope?"""
    cmap = stretch_cmap("jet", range(10))
    assert cmap is not None
    cmap = dep_erosion()
    assert cmap is not None
