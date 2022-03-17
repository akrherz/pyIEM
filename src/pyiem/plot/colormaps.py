"""Definition of colormaps"""
import copy
import os

import numpy as np
import matplotlib.cm as cm
import matplotlib.colors as mpcolors

# Local
from pyiem.reference import DATADIR


def _register_cmap(cmap):
    """Workaround tricky matplotlib API.

    see matplotlib/matplotlib#19842
    """
    hascmap = False
    try:
        cm.get_cmap(cmap.name)
        hascmap = True
    except ValueError:
        pass
    if not hascmap:
        cm.register_cmap(cmap=cmap)
    return hascmap


def _load_local_cmap_colors(name):
    """Return list of colors for this cmap from local file."""
    fn = os.path.join(DATADIR, "..", "cmap", f"{name}.txt")
    with open(fn, encoding="utf8") as fh:
        res = fh.read().strip().split("\n")
    return res


def get_cmap(name, *args, **kwargs):
    """Matplotlib `get_cmap()` proxy to deal with API complexity."""
    return copy.copy(cm.get_cmap(name, *args, **kwargs))


def stretch_cmap(cmap, bins, extend="both"):
    """Return a cmap with appropriate over,under,bad settings.

    The issue at hand is that default color ramps do not properly extend to
    cover over and under using values from the color ramp.  That is desired
    behaviour of this library.  If over,under,bad is already set, those
    settings are retained.

    Args:
      cmap (cm.ColorMap): inbound colormap
      bins (list): values for binning
      extend (str): either 'both', 'neither', 'min', 'max' to control cbar

    Retuns:
      cm.ColorMap
    """
    if cmap is None:
        cmap = maue()
    if isinstance(cmap, str):
        cmap = cm.get_cmap(cmap)
    if extend not in ["both", "neither", "min", "max"]:
        extend = "both"

    # get effectively two more colors than necessary
    colors = cmap(np.arange(len(bins) + 1) / float(len(bins)))
    # create a new cmap, skipping first and last
    cmapout = mpcolors.ListedColormap(colors[1:-1], "")
    # pylint: disable=W0212
    cmapout.set_bad(cmap._rgba_bad)
    if extend in ["both", "max"]:
        cmapout.set_over(cmap._rgba_over or colors[-1])
    if extend in ["both", "min"]:
        cmapout.set_under(cmap._rgba_under or colors[0])
    # we can now return
    return cmapout


def nwsprecip():
    """A color ramp used by NWS on NTP plots

    Changes
     - modified the reds a bit to provide a larger gradient
     - added two light brown colors at the low end to allow for more levels
     - removed perhaps a bad orange color and remove top white color
    """
    cpool = [
        "#cbcb97",
        "#989865",
        "#00ebe7",
        "#00a0f5",
        "#000df5",
        "#00ff00",
        "#00c600",
        "#008e00",
        "#fef700",
        "#e5bc00",
        "#ff8500",
        "#ff0000",
        "#af0000",
        "#640000",
        "#ff00fe",
        "#a152bc",
    ]
    cmap = mpcolors.ListedColormap(cpool, "nwsprecip")
    cmap.set_over("#FFFFFF")
    cmap.set_under("#FFFFFF")
    cmap.set_bad("#FFFFFF")
    _register_cmap(cmap)
    return cmap


def nwssnow():
    """A Color Ramp Suggested by the NWS for Snowfall"""
    cpool = [
        [0.74117647, 0.84313725, 0.90588235],
        [0.41960784, 0.68235294, 0.83921569],
        [0.19215686, 0.50980392, 0.74117647],
        [0.03137255, 0.31764706, 0.61176471],
        [0.03137255, 0.14901961, 0.58039216],
        [1.0, 1.0, 0.58823529],
        [1.0, 0.76862745, 0.0],
        [1.0, 0.52941176, 0.0],
        [0.85882353, 0.07843137, 0.0],
        [0.61960784, 0.0, 0.0],
        [0.41176471, 0.0, 0.0],
    ]
    cmap = mpcolors.ListedColormap(cpool, "nwssnow")
    cmap.set_over([0.16862745, 0.0, 0.18039216])
    cmap.set_under("#FFFFFF")
    cmap.set_bad("#FFFFFF")
    _register_cmap(cmap)
    return cmap


def _gen(name, cpool):
    """Generator Helper."""
    cmap = mpcolors.ListedColormap(cpool, name)
    cmap.set_over("#000000")
    cmap.set_under("#FFFFFF")
    cmap.set_bad("#FFFFFF")
    _register_cmap(cmap)
    return cmap


def dep_erosion():
    """DEP Erosion ramp yelllow to brown (jump at 5T) `cool`"""
    # NB: dep.RAMPS wants just 8 colors, so don't define more than that here
    cpool = [
        "#FFFF80",
        "#FCDD60",
        "#E69729",
        "#B35915",
        "#822507",
        "#00ffff",
        "#55aaff",
        "#d52aff",
    ]
    return _gen("dep_erosion", cpool)


def james2():
    """David James suggested color ramp Yellow to Brown"""
    cpool = [
        "#FFFF80",
        "#FFEE70",
        "#FCDD60",
        "#FACD52",
        "#F7BE43",
        "#F5AF36",
        "#E69729",
        "#CC781F",
        "#B35915",
        "#9C400E",
        "#822507",
        "#6B0000",
    ]
    return _gen("james2", cpool)


def james():
    """David James suggested color ramp Yellow to Blue"""
    cpool = [
        "#FFFF80",
        "#CDFA64",
        "#98F046",
        "#61E827",
        "#3BD923",
        "#3FC453",
        "#37AD7A",
        "#26989E",
        "#217AA3",
        "#215394",
        "#1B3187",
        "#0C1078",
    ]
    return _gen("james", cpool)


def whitebluegreenyellowred():
    """Rip off NCL's WhiteBlueGreenYellowRed"""
    cpool = _load_local_cmap_colors("whitebluegreenyellowred")
    cmap3 = mpcolors.ListedColormap(cpool, "whitebluegreenyellowred")
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    _register_cmap(cmap=cmap3)
    return cmap3


def maue():
    """Pretty color ramp Dr Ryan Maue uses"""
    cpool = _load_local_cmap_colors("maue")
    cmap3 = mpcolors.ListedColormap(cpool, "maue")
    _register_cmap(cmap=cmap3)
    return cmap3
