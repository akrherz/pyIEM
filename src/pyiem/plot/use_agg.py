"""A utility to load matplotlib and set the backend to AGG."""

# pylint: disable=unused-import,wrong-import-position
import os

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from pandas.plotting import register_matplotlib_converters

matplotlib.use("agg")

# Workaround a pandas dataframe to matplotlib issue
register_matplotlib_converters()

# work around warning coming from pooch
if "TEST_DATA_DIR" not in os.environ:
    os.environ["TEST_DATA_DIR"] = "/tmp"


class _NoIdleDrawCanvas(FigureCanvasAgg):
    """Agg canvas whose ``draw_idle`` is a no-op.

    On Agg, ``draw_idle`` renders the whole figure immediately.  Artists
    marking the figure stale (for example each geopandas ``plot`` call) would
    otherwise trigger a full render per call.  Rendering still happens on
    explicit ``draw``, ``savefig``, or renderer-based extent requests.
    """

    def draw_idle(self, *args, **kwargs):
        """Do nothing, there is no event loop to defer to."""


def figure(**kwargs) -> Figure:
    """Create a new figure using matplotlib's OO API.

    Args:
        **kwargs: Arguments to pass to Figure constructor

    Returns:
        matplotlib.figure.Figure: The created figure
    """
    fig = matplotlib.figure.Figure(**kwargs)
    canvas = _NoIdleDrawCanvas(fig)
    fig.set_canvas(canvas)
    return fig


__all__ = ["figure"]
