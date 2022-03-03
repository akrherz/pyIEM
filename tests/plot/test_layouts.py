"""Test pyiem.plot.layouts."""

# third party
import pytest

# local
from pyiem.plot.use_agg import plt
from pyiem.plot.layouts import figure_axes, figure


def test_provided_fig():
    """Test that figsize gets set properly."""
    fig = plt.figure()
    figure(fig=fig, apctx={"_r": "169"})
    assert fig.get_size_inches()[0] == 12.8


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_dpi():
    """Test setting a dpi via autoplot context."""
    fig, ax = figure_axes(
        apctx={"_r": "169", "_dpi": "30"},
    )
    ax.plot([0, 1], [0, 1])
    return fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_crawl_before_walk():
    """Test that we can do basic things."""
    fig, ax = figure_axes(
        title="This is my Fancy Pants Title.",
        subtitle="This is my Fancy Pants SubTitle.",
    )
    ax.plot([0, 1], [0, 1])
    return fig


def test_figsize():
    """Test that figsize gets set properly."""
    fig = figure(apctx={"_r": "169"})
    assert fig.get_size_inches()[0] == 12.8
