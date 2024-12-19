"""Test stage4 information."""

from pyiem import stage4


def test_axis_spacing():
    """Test that linspace is correct."""
    assert abs(stage4.XAXIS[1] - (stage4.XAXIS[0] + stage4.DX)) < 0.1
    assert abs(stage4.YAXIS[1] - (stage4.YAXIS[0] + stage4.DY)) < 0.1


def test_axis_points():
    """Test that the axis points are correct."""
    x0 = stage4.XAXIS[0]
    y0 = stage4.YAXIS[0]
    # pygrib says this is the lower left corner
    x, y = stage4.PROJ(-119.023, 23.117)
    # Shirely 2 meters is close enough
    assert abs(x - x0) < 2
    assert abs(y - y0) < 2
    # pygrib says this is the upper right corner
    x1 = stage4.XAXIS[-1]
    y1 = stage4.YAXIS[-1]
    x, y = stage4.PROJ(-59.95936, 45.61939)
    assert abs(x - x1) < 2
    assert abs(y - y1) < 2


def test_find_ij():
    """Test the find_ij function."""
    # pygrib says this is the lower left corner
    i, j = stage4.find_ij(-119.02, 23.117)
    assert i == 0
    assert j == 0
    # this still should be in that grid cell
    i, j = stage4.find_ij(-119.03, 23.10)
    assert i == 0
    assert j == 0
    # this still should not be in that grid cell
    i, j = stage4.find_ij(-119.07, 23.06)
    assert i is None
    assert j is None
