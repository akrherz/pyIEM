"""Can we make windrose plots?"""

import pytest
import numpy as np
from metpy.units import units
from pyiem.plot import get_cmap
from pyiem.plot.windrose import WindrosePlot, histogram, plot

BINS = np.array([2, 5, 7, 10, 15, 20]) * units("mph")
SPEED = np.arange(0, 60, 0.1) * units("meter / second")
DIRECTION = SPEED.m * 6.0 * units("degree")
TOLERANCE = 0.1


@pytest.mark.mpl_image_compare(tolerance=TOLERANCE)
def test_windrose_figsize():
    """Test setting figsize via apctx."""
    wr = plot(
        DIRECTION,
        SPEED,
        bins=BINS,
        nsector=16,
        cmap=get_cmap("jet"),
        title="Hello Friends, Welcome to the Masters!",
        apctx={"_r": "t"},
    )
    # Some diagnostics
    ax = wr.fig.add_axes([0, 0, 1, 1], frameon=False, xticks=[], yticks=[])
    ax.axhline(0.9)
    ax.axhline(0.1)
    return wr.fig


def test_draw_logo_deprecation():
    """draw_logo is done."""
    wr = WindrosePlot()
    with pytest.raises(DeprecationWarning):
        wr.draw_logo()


@pytest.mark.mpl_image_compare(tolerance=TOLERANCE)
def test_windrose_basic():
    """Can we crawl."""
    wr = WindrosePlot()
    return wr.fig


@pytest.mark.mpl_image_compare(tolerance=TOLERANCE)
def test_windrose_barplot_noopts():
    """Generate a plot with defaults for bins."""
    wr = plot(DIRECTION, SPEED, rmax=10)
    return wr.fig


@pytest.mark.mpl_image_compare(tolerance=TOLERANCE)
def test_windrose_barplot():
    """Can we crawl."""
    wr = plot(DIRECTION, SPEED, bins=BINS, nsector=16)
    return wr.fig


@pytest.mark.mpl_image_compare(tolerance=TOLERANCE)
def test_windrose_barplot_jet():
    """Test with providing my own cmap."""
    wr = plot(DIRECTION, SPEED, bins=BINS, nsector=16, cmap=get_cmap("jet"))
    return wr.fig


def test_histogram():
    """Can we make histograms properly."""
    nsector = 16
    calm_percent, dirbins, table = histogram(SPEED, DIRECTION, BINS, nsector)
    # 9 out of 600 above are below 2 MPH, 1.5%
    assert abs(calm_percent.m - 1.50) < 0.01
    assert dirbins.m.shape[0] == table.m.shape[0]
