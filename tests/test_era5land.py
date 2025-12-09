"""Test the logic in pyiem.era5land"""

from pyiem import era5land


def test_grid():
    """Test that the grid is rectified to 0.1 degree."""
    for pt in era5land.DOMAINS["conus"]["XAXIS"]:
        assert abs(pt - round(pt, 1)) < 0.01


def test_find_ij():
    """Test that we can find the grid cell for a given lon/lat."""
    i, j = era5land.find_ij(-94.5, -41.5)
    assert i is None and j is None

    lon = -94.5
    lat = 41.5
    i, j = era5land.find_ij(lon, lat)
    assert abs(lon - era5land.DOMAINS["conus"]["XAXIS"][i]) < 0.01
    assert abs(lat - era5land.DOMAINS["conus"]["YAXIS"][j]) < 0.01
