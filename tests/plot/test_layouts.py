"""Test pyiem.plot.layouts."""

# third party
import pytest

# local
from pyiem.plot.layouts import figure_axes


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_crawl_before_walk():
    """Test that we can do basic things."""
    fig, ax = figure_axes(
        title="This is my Fancy Pants Title.",
        subtitle="This is my Fancy Pants SubTitle.",
    )
    ax.plot([0, 1], [0, 1])
    return fig
