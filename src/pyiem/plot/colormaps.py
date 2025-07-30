"""Definition of colormaps"""

import os

import numpy as np
from matplotlib import colormaps
from matplotlib import colors as mpcolors

# Local
from pyiem.reference import DATADIR
from pyiem.util import LOG


def _register_cmap(cmap):
    """Workaround tricky matplotlib API.

    see matplotlib/matplotlib#19842
    """
    hascmap = False
    try:
        get_cmap(cmap.name)
        hascmap = True
    except KeyError:
        LOG.debug("Failed to get cmap: %s", cmap.name)
    if not hascmap:
        colormaps.register(cmap)
    return hascmap


def _load_local_cmap_colors(name):
    """Return list of colors for this cmap from local file."""
    fn = os.path.join(DATADIR, "..", "cmap", f"{name}.txt")
    with open(fn, encoding="utf8") as fh:
        return fh.read().strip().split("\n")


def get_cmap(name):
    """Helper to workaround matplotlib complexity."""
    return colormaps[name]


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
        cmap = get_cmap(cmap)
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
    cpool = (
        "#cbcb97 #989865 #00ebe7 #00a0f5 #000df5 #00ff00 #00c600 #008e00 "
        "#fef700 #e5bc00 #ff8500 #ff0000 #af0000 #640000 #ff00fe #a152bc"
    ).split()
    cmap = mpcolors.ListedColormap(cpool, "nwsprecip")
    cmap.set_over("#FFFFFF")
    cmap.set_under("#FFFFFF")
    cmap.set_bad("#FFFFFF")
    _register_cmap(cmap)
    return cmap


def nwsice():
    """A Color Ramp Suggested by the NWS for Ice Accumulation."""
    cpool = [
        "#f4ea3b",  # 0-0.1
        "#ffc000",  # 0.1-0.25
        "#fe0000",  # 0.25-0.5
        "#c00000",  # 0.5-0.75
        "#9966ff",  # 0.75-1
        "#730ac7",  # 1-2
    ]
    cmap = mpcolors.ListedColormap(cpool, "nwsice")
    cmap.set_over("#25045b")  # 2+
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
    cpool = (
        "#FFFF80 #FCDD60 #E69729 #B35915 #822507 #00ffff #55aaff #d52aff"
    ).split()
    return _gen("dep_erosion", cpool)


def james2():
    """David James suggested color ramp Yellow to Brown"""
    cpool = (
        "#FFFF80 #FFEE70 #FCDD60 #FACD52 #F7BE43 #F5AF36 #E69729 #CC781F "
        "#B35915 #9C400E #822507 #6B0000"
    ).split()
    return _gen("james2", cpool)


def james():
    """David James suggested color ramp Yellow to Blue"""
    cpool = (
        "#FFFF80 #CDFA64 #98F046 #61E827 #3BD923 #3FC453 #37AD7A #26989E "
        "#217AA3 #215394 #1B3187 #0C1078"
    ).split()
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


def radar_ptype() -> dict[str, list]:
    """Generate a dictionary of colors for HRRR Ptype."""
    return {
        "rain": (
            # 0-40 by 2.5, Green
            "#eef8ea #e5f5e0 #d6efd0 #c7e9c0 #b4e1ad #a0d99b #8ace88 #73c476 "
            "#5ab769 #40aa5d #319a50 #228a44 #117b38 #006c2c #005723 #00441b "
            # 40-55 by 2.5, Wistia
            "#ffe81a #ffd710 #ffc505 #ffb700 #ffab00 #ffa000"
        ).split(),
        "snow": (
            # 0-40 by 2.5, 16 colors from ocean_r
            "#b4dae6 #99ccdd #81c0d5 #66b3cc #4ea6c4 #3399bb #1b8db3 #0080aa "
            "#0073a2 #006699 #005a91 #004d88 #003f7f #003377 #00266e #001a66 "
            # 40-55 by 2.5, 6 colors from PuRd_r
            "#8d003b #b80b4e #d81b6a #e53592 #df66b0 #cd8bc2"
        ).split(),
        "frzr": (
            # 0-55 by 2.5, 22 colors Reds
            "#ffeee6 #fee6da #fedecf #fdd0bc #fcc2aa #fcb499 #fca588 #fc9576 "
            "#fc8767 #fb7858 #fb694a #f7593f #f24734 #ec382b #de2b25 #d11e1f "
            "#c4161c #b61319 #a81016 #940b13 #7c0510 #67000d"
        ).split(),
        "icep": (
            # 0-55 by 2.5, 22 colors Purples
            "#f8f6fa #f3f1f7 #eeecf4 #e6e5f1 #dedded #d5d5e9 #cacae3 #bebfdd "
            "#b4b4d7 #a9a7cf #9e9ac8 #9390c3 #8885be #7e79b8 #7669af #6e58a7 "
            "#66499f #5e3a98 #552a90 #4e1c8a #460d83 #3f007d"
        ).split(),
    }
