"""Can we make windrose plots?"""

import pytest
import numpy as np
from metpy.units import units
from pyiem.plot.windrose import WindrosePlot, histogram, plot


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_basic():
    """Can we crawl."""
    wr = WindrosePlot()
    return wr.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_barplot():
    """Can we crawl."""
    nsector = 16
    bins = np.array([2, 5, 10, 20]) * units("mph")
    speed = np.arange(0, 60, 0.1) * units("meter / second")
    direction = speed.m * 6.0 * units("degree")
    wr = plot(direction, speed, bins=bins, nsector=nsector)
    return wr.fig


def test_histogram():
    """Can we make histograms properly."""
    nsector = 16
    bins = np.array([2, 5, 10, 20]) * units("mph")
    speed = np.arange(0, 60, 0.1) * units("meter / second")
    direction = speed.m * 6.0 * units("degree")
    calm_percent, dirbins, table = histogram(speed, direction, bins, nsector)
    assert abs(calm_percent.m - 1.50) < 0.01
    assert dirbins.m.shape[0] == table.m.shape[0]
