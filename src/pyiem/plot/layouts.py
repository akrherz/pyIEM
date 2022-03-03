"""Standardized layouts."""

# local
from pyiem.reference import TWITTER_RESOLUTION_INCH
from pyiem.plot.use_agg import plt
from pyiem.plot.util import draw_logo, fitbox, update_kwargs_apctx


@update_kwargs_apctx
def figure(logo="iem", title=None, subtitle=None, **kwargs):
    """Return an opinionated matplotlib figure.

    Parameters:
      figsize (width, height): in inches for the figure, defaults to something
        good for twitter.
      dpi (int): dots per inch
      logo (str): Currently, 'iem', 'dep' is supported. `None` disables.
      title (str): Title to place on the figure.
      subtitle (str): SubTitle to place on the figure.
      apctx (dict, optional): autoplot context.
      fig (matplotlib.figure.Figure): Figure passed in for modification for
        figsize only currently.
    """
    kwargs.pop("apctx", None)
    kwargs["figsize"] = kwargs.get("figsize", TWITTER_RESOLUTION_INCH)
    fig = kwargs.pop("fig", None)
    if fig is None:
        fig = plt.figure(**kwargs)
    else:
        fig.set_size_inches(kwargs["figsize"])
    draw_logo(fig, logo)
    titlebounds = [0.1, 0.98, 0.91, 0.98]
    if subtitle is not None:
        titlebounds[2] = 0.94
    fitbox(fig, title, *titlebounds)
    fitbox(fig, subtitle, 0.1, 0.98, 0.91, 0.935)
    return fig


def figure_axes(logo="iem", title=None, subtitle=None, **kwargs):
    """Return an opinionated matplotlib figure and one axes.

    Parameters:
      figsize (width, height): in inches for the figure, defaults to something
        good for twitter.
      dpi (int): dots per inch
      logo (str): Currently, 'iem', 'dep' is supported. `None` disables.
      title (str): Title to place on the figure.
      subtitle (str): SubTitle to place on the figure.
    """
    fig = figure(logo=logo, title=title, subtitle=subtitle, **kwargs)
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8])
    return fig, ax
