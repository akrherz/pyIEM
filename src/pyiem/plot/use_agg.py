"""A utility to load matplotlib and set the backend to AGG."""

# pylint: disable=unused-import,wrong-import-position
import os

import matplotlib
from matplotlib.figure import Figure
from pandas.plotting import register_matplotlib_converters

matplotlib.use("agg")

# Workaround a pandas dataframe to matplotlib issue
register_matplotlib_converters()

# work around warning coming from pooch
if "TEST_DATA_DIR" not in os.environ:
    os.environ["TEST_DATA_DIR"] = "/tmp"


def figure(**kwargs) -> Figure:
    """Create a new figure using matplotlib's OO API.

    Args:
        **kwargs: Arguments to pass to Figure constructor

    Returns:
        matplotlib.figure.Figure: The created figure
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = matplotlib.figure.Figure(**kwargs)
    canvas = FigureCanvasAgg(fig)
    fig.set_canvas(canvas)
    return fig


__all__ = ["figure"]
