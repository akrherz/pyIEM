"""Can we make windrose plots?"""

import pytest
import numpy as np
from metpy.units import units
from pyiem.plot.windrose import WindrosePlot, histogram, plot

BINS = np.array([2, 5, 10, 20]) * units("mph")
SPEED = np.arange(0, 60, 0.1) * units("meter / second")
DIRECTION = SPEED.m * 6.0 * units("degree")


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_basic():
    """Can we crawl."""
    wr = WindrosePlot()
    return wr.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_barplot_noopts():
    """Generate a plot with defaults for bins."""
    wr = plot(DIRECTION, SPEED, rmax=10)
    return wr.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_barplot():
    """Can we crawl."""
    wr = plot(DIRECTION, SPEED, bins=BINS, nsector=16)
    return wr.fig


def test_histogram():
    """Can we make histograms properly."""
    nsector = 16
    calm_percent, dirbins, table = histogram(SPEED, DIRECTION, BINS, nsector)
    # 9 out of 600 above are below 2 MPH, 1.5%
    assert abs(calm_percent.m - 1.50) < 0.01
    assert dirbins.m.shape[0] == table.m.shape[0]
