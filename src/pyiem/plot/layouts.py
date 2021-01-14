"""Standardized layouts."""

# local
from pyiem.reference import TWITTER_RESOLUTION_INCH
from pyiem.plot.use_agg import plt
from pyiem.plot.util import draw_logo, fitbox


def figure(figsize=None, logo="iem", title=None, subtitle=None, **kwargs):
    """Return an opinionated matplotlib figure.

    Parameters:
      figsize (width, height): in inches for the figure, defaults to something
        good for twitter.
      dpi (int): dots per inch
      logo (str): Currently, 'iem', 'dep' is supported. `None` disables.
      title (str): Title to place on the figure.
      subtitle (str): SubTitle to place on the figure.
    """
    if figsize is None:
        figsize = TWITTER_RESOLUTION_INCH
    fig = plt.figure(figsize=figsize, **kwargs)
    draw_logo(fig, logo)
    titlebounds = [0.1, 0.9, 0.91, 0.98]
    if subtitle is not None:
        titlebounds[2] = 0.94
    fitbox(fig, title, *titlebounds)
    fitbox(fig, subtitle, 0.1, 0.9, 0.91, 0.935)
    return fig


def figure_axes(figsize=None, logo="iem", title=None, subtitle=None, **kwargs):
    """Return an opinionated matplotlib figure and one axes.

    Parameters:
      figsize (width, height): in inches for the figure, defaults to something
        good for twitter.
      dpi (int): dots per inch
      logo (str): Currently, 'iem', 'dep' is supported. `None` disables.
      title (str): Title to place on the figure.
      subtitle (str): SubTitle to place on the figure.
    """
    fig = figure(figsize, logo, title, subtitle, **kwargs)
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])
    return fig, ax
