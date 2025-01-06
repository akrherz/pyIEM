"""Plotting"""
# This was a bad idea, but we are stuck with it for now.

from .calendarplot import calendar_plot  # noqa
from .colormaps import (
    get_cmap,  # noqa
    nwsice,  # noqa
    nwsprecip,  # noqa
    nwssnow,  # noqa
)
from .geoplot import (
    MapPlot,  # noqa
)
from .layouts import figure, figure_axes  # noqa
from .util import (
    centered_bins,  # noqa
    fitbox,  # noqa
    pretty_bins,  # noqa
    ramp2df,  # noqa
)
