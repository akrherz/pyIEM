"""test our colormaps.py"""
from pyiem.plot.colormaps import stretch_cmap


def test_stretch():
    """can we do what we hope?"""
    cmap = stretch_cmap('jet', range(10))
    assert cmap is not None
