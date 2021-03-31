# -*- coding: utf-8 -*-
# pylint: disable=import-outside-toplevel,too-many-lines
"""Plotting utility for generating maps, windroses and everything else under
the sun.

This module provides a wrapper around `Basemap` and `windrose` packages.  It
tries to be general so to work for others, but may contain some unfortunate
hard coded values.  Bad daryl!

Example:
    Here is a basic example of usage.

    >>> from pyiem.plot.geoplot import MapPlot
    >>> m = MapPlot(sector='conus', title='My Fancy Title')
    >>> m.postprocess(filename='myplot.png')
    >>> m.close()

"""
# stdlib
from io import BytesIO
import tempfile
import os
import sys
import subprocess
import shutil
import datetime
import warnings

# third party
import rasterio
from rasterio.warp import reproject, Resampling
import requests
from metpy.calc import wind_components
from metpy.units import units
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from scipy.signal import convolve2d
from scipy.interpolate import NearestNDInterpolator
from PIL import Image
import matplotlib.colors as mpcolors
from matplotlib.patches import Wedge
import matplotlib.colorbar as mpcolorbar
import matplotlib.patheffects as PathEffects
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# local
from pyiem.plot.use_agg import plt
from pyiem.plot.util import (
    sector_setter,
    mask_outside_polygon,
    polygon_fill,
    mask_outside_geom,
    draw_logo,
    fitbox,
)
from pyiem.reference import (  # noqa: F401  # pylint: disable=unused-import
    LATLON,
    Z_CF,
    Z_FILL,
    Z_FILL_LABEL,
    Z_CLIP,
    Z_CLIP2,
    Z_POLITICAL,
    Z_OVERLAY,
    Z_OVERLAY2,
    Z_FRAME,
    TWITTER_RESOLUTION_INCH,
)
from pyiem.util import ssw, LOG, utc, exponential_backoff, load_geodf
from pyiem.plot.colormaps import stretch_cmap

# geopandas currently emits this as parquet is unstable.
warnings.filterwarnings("ignore", message=".*implementation of Parquet.*")
# we ran the cartopy/tools downloader
cartopy.config["pre_existing_data_dir"] = "/opt/miniconda3/cartopy_data/"
# Set a saner default for apache et al
cartopy.config["data_dir"] = "/tmp/"


DATADIR = os.sep.join([os.path.dirname(__file__), "..", "data"])
MAIN_AX_BOUNDS = [0.01, 0.05, 0.898, 0.85]
CAX_BOUNDS = [0.917, 0.1, 0.02, 0.8]


def load_bounds(filebase):
    """Load bounds file

    Args:
      filebase (str): the basename of the file containing the data

    Returns:
      numpy 2d array of the data
    """
    fn = "%s/%s.npy" % (DATADIR, filebase)
    if not os.path.isfile(fn):
        LOG.info("load_bounds(%s) is missing!", fn)
        return
    return np.load(fn)


def load_pickle_pd(filename):
    """Load a pickled pandas dataframe

    Args:
      filename(str): The filename to load, relative to project data/

    Returns:
      pandas.DataFrame
    """
    fn = "%s/%s" % (DATADIR, filename)
    if not os.path.isfile(fn):
        LOG.info("load_pickle_pd(%s) failed, file is missing", fn)
        return
    return pd.read_pickle(fn)


class MapPlot:
    """An object representing a cartopy plot.

    An object that allows one to quickly and easily generate map plots of data
    with some customization possible.  This is what drives most of the plots
    you see on the IEM website.

    Example:
      Here is an example of usage::

        mplot = MapPlot(sector='midwest', title='My Plot Title')
        mplot.plot_values([-99,-95], [44,45], ['hi','there'])
        mplot.postprocess(filename='test.png')
        mplot.close()

    Attributes:
        fig (matplotlib.Figure): figure object
        ax (matplotlib.Axes): main figure plot axes

    """

    def __init__(self, sector="iowa", figsize=(10.24, 7.68), **kwargs):
        """Construct a MapPlot

        Args:
          sector (str): plot domain, set 'custom' to bring your own projection
          kwargs:
            projection (cartopy.crs,optional): bring your own projection
            north (float,optional): Plot top bounds (degN Lat)
            south (float,optional): Plot bottom bounds (degN Lat)
            east (float,optional): Plot right bounds (degE Lon)
            west (float,optional): Plot left bounds (degE Lon)
            titlefontsize (int): fontsize to use for the plot title
            subtitlefontsize (int): fontsize to use for the plot subtitle
            continentalcolor (color): color to use for continental coloring
            debug (bool): enable debugging
            aspect (str): plot aspect, defaults to equal
            fig (matplotlib.pyplot.figure,optional): provide a figure instance
              for more advanced plot control.
            logo (str,optional): logo name to slap on the plot.
            twitter (bool): Set an image resolution that is favorable to
              posting to Twitter. Default: False.
        """
        self.debug = kwargs.get("debug", False)
        self.fig = kwargs.get("fig")
        if kwargs.get("twitter", False) is True:
            figsize = TWITTER_RESOLUTION_INCH
        if self.fig is None:
            self.fig = plt.figure(
                num=None, figsize=figsize, dpi=kwargs.get("dpi", 100)
            )
        # Storage of axes within this plot
        self.state = None
        self.cwa = None
        self.textmask = None  # For our plot_values magic, to prevent overlap
        self.sector = sector
        self.cax = plt.axes(CAX_BOUNDS, frameon=False, yticks=[], xticks=[])
        self.axes = []
        self.ax = None
        self.pr_ax = None
        self.hi_ax = None
        self.ak_ax = None
        # hack around sector=iowa
        if self.sector == "iowa":
            self.sector = "state"
            self.state = "IA"
        sector_setter(self, MAIN_AX_BOUNDS, **kwargs)

        for _a in self.axes:
            if _a is None:
                continue
            # legacy usage of axisbg here
            _c = kwargs.get(
                "axisbg", kwargs.get("continentalcolor", "#EEEEEE")
            )
            _a.add_feature(cfeature.LAND, facecolor=_c, zorder=Z_CF)
            _a.add_feature(cfeature.COASTLINE, lw=1.0, zorder=Z_POLITICAL)
            _a.add_feature(cfeature.BORDERS, lw=1.0, zorder=Z_POLITICAL)
            _a.add_feature(
                cfeature.LAKES, facecolor=(0.4471, 0.6235, 0.8117), zorder=Z_CF
            )
            if "nostates" not in kwargs:
                states = load_geodf("us_states")
                _a.add_geometries(
                    states["geom"].values,
                    crs=ccrs.PlateCarree(),
                    lw=1.0,
                    edgecolor=kwargs.get("statebordercolor", "k"),
                    facecolor="None",
                    zorder=Z_POLITICAL,
                )

        if not kwargs.get("nologo", False):
            draw_logo(self.fig, kwargs.get("logo", "iem"))
        if "title" in kwargs:
            fitbox(
                self.fig,
                kwargs.get("title"),
                0.09 if not kwargs.get("nologo") else 0.02,
                0.99,
                0.94,
                0.99,
                textsize=kwargs.get("titlefontsize", 18),
            )
        if "subtitle" in kwargs:
            fitbox(
                self.fig,
                kwargs.get("subtitle"),
                0.09 if not kwargs.get("nologo") else 0.02,
                0.99,
                0.91,
                0.94,
                textsize=kwargs.get("subtitlefontsize", 12),
            )

        if "nocaption" not in kwargs:
            self.fig.text(
                0.01,
                0.03,
                ("%s :: generated %s")
                % (
                    kwargs.get("caption", "Iowa Environmental Mesonet"),
                    datetime.datetime.now().strftime("%d %B %Y %I:%M %p %Z"),
                ),
            )

    def close(self):
        """ Close the figure in the case of batch processing """
        plt.close()

    def draw_usdm(self, valid=None, filled=True, hatched=False):
        """Overlay the US Drought Monitor

        This utilizes a GeoJSON web service provided by the IEM.  The provided
        date to this method is passed to the web service which rectifies the
        date to provide the USDM analysis valid for that date.  If no date
        is specified, the current analysis is plotted.

        Args:
          valid (str or datetime.date): The valid time to plot this USDM
          filled (boolean): Should we draw lines or filled polygons
          hatched (boolean): Should we use hatch filling

        Return:
          date that the USDM is valid for
        """
        colors = ["#ffff00", "#fcd37f", "#ffaa00", "#e60000", "#730000"]
        hatches = ["+", "/", "\\", "-", "x"]
        if valid is None:
            valid = ""
        elif isinstance(valid, datetime.date):
            valid = valid.strftime("%Y-%m-%d")
        elif isinstance(valid, datetime.datetime):
            valid = valid.strftime("%Y-%m-%d")
        url = ("http://mesonet.agron.iastate.edu/geojson/usdm.py?date=%s") % (
            valid,
        )
        try:
            req = requests.get(url, timeout=30)
        except requests.ConnectionError as exp:
            warnings.warn("draw_usdm IEM USDM Webservice failed: %s" % (exp,))
            return None
        df = gpd.GeoDataFrame().from_features(req.json())
        lw = 1 if filled else 4.0
        usdm_valid = None
        for _, row in df.iterrows():
            color = colors[row["dm"]]
            geom = shape(row["geometry"])
            usdm_valid = row["date"]
            fc = color if filled else "None"
            ec = color if not filled else "k"
            self.ax.add_geometries(
                [geom],
                ccrs.PlateCarree(),
                facecolor="None",
                edgecolor=ec,
                linewidth=lw,
                zorder=Z_OVERLAY2,
            )
            if filled:
                self.ax.add_geometries(
                    [geom],
                    ccrs.PlateCarree(),
                    facecolor=fc,
                    alpha=0.5,
                    edgecolor="None",
                    zorder=Z_OVERLAY,
                )
            elif hatched:
                self.ax.add_geometries(
                    [geom],
                    ccrs.PlateCarree(),
                    facecolor="None",
                    hatch=hatches[row["dm"]],
                    edgecolor=color,
                    zorder=Z_OVERLAY2 + 2,
                )

        if usdm_valid is not None:
            self.ax.text(
                0.99,
                0.99,
                "D4",
                color="k",
                transform=self.ax.transAxes,
                va="top",
                ha="right",
                bbox=dict(color=colors[4]),
                zorder=Z_OVERLAY2 + 3,
            )
            self.ax.text(
                0.955,
                0.99,
                "D3",
                color="k",
                transform=self.ax.transAxes,
                va="top",
                ha="right",
                bbox=dict(color=colors[3]),
                zorder=Z_OVERLAY2 + 3,
            )
            self.ax.text(
                0.92,
                0.99,
                "D2",
                color="k",
                transform=self.ax.transAxes,
                va="top",
                ha="right",
                bbox=dict(color=colors[2]),
                zorder=Z_OVERLAY2 + 3,
            )
            self.ax.text(
                0.885,
                0.99,
                "D1",
                color="k",
                transform=self.ax.transAxes,
                va="top",
                ha="right",
                bbox=dict(color=colors[1]),
                zorder=Z_OVERLAY2 + 3,
            )
            self.ax.text(
                0.85,
                0.99,
                "D0",
                color="k",
                transform=self.ax.transAxes,
                va="top",
                ha="right",
                bbox=dict(color=colors[0]),
                zorder=Z_OVERLAY2 + 3,
            )
            self.ax.text(
                0.815,
                0.99,
                "USDM %s" % (usdm_valid,),
                color="w",
                transform=self.ax.transAxes,
                va="top",
                ha="right",
                bbox=dict(color="k"),
                zorder=Z_OVERLAY2 + 3,
            )
            return datetime.datetime.strptime(usdm_valid, "%Y-%m-%d")
        return None

    def draw_colorbar(self, clevs, cmap, norm, **kwargs):
        """Draw the colorbar on the structed plot using `self.cax`.

        Args:
          clevs (list): The levels used in the classification
          cmap (matplotlib.colormap): The colormap
          norm (normalize): The value normalizer
          title (str,optional): Place a label on the side, adjusts the plot
            accordingly to allow this text to fit, no multiline please!
          spacing (str,optional): should the colorbar be `uniform` or
            `proportional`, defaults to `uniform`
        """
        if self.cax is None:
            return
        extend = kwargs.get("extend", "both")
        # Do we need to muck with the cmap
        # pylint: disable=W0212
        if (extend in ["max", "both"] and cmap._rgba_over is None) or (
            extend in ["min", "both"] and cmap._rgba_under is None
        ):
            cmap = stretch_cmap(cmap, clevs, extend=extend)
            norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        clevlabels = kwargs.get("clevlabels", clevs)

        under = clevs[0] - (clevs[1] - clevs[0])
        over = clevs[-1] + (clevs[-1] - clevs[-2])
        # create some faked levels in case we want an extended colorbar
        if extend == "min":
            blevels = np.concatenate([[under], clevs])
        elif extend == "max":
            blevels = np.concatenate([clevs, [over]])
        elif extend == "both":
            blevels = np.concatenate([[under], clevs, [over]])
        else:
            blevels = clevs
        stride = slice(None, None, int(kwargs.get("clevstride", 1)))
        cb2 = mpcolorbar.ColorbarBase(
            self.cax,
            cmap=cmap,
            norm=norm,
            boundaries=blevels,
            extend=extend,
            ticks=clevs[stride],
            spacing=kwargs.get("spacing", "uniform"),
            orientation="vertical",
        )

        def _myrepr(val):
            """avoid list conversion in matplotlib that fowls numpy floats."""
            try:
                return "%g" % (val,)
            except TypeError:
                return "%s" % (val,)

        cb2.ax.set_yticklabels(list(map(_myrepr, clevlabels[stride])))
        # Attempt to quell offset that sometimes appears with large numbers
        cb2.ax.get_yaxis().get_major_formatter().set_offset_string("")
        for label in cb2.ax.get_yticklabels():
            sz = len(label.get_text())
            if sz > 4:
                label.set_fontsize(12)
            else:
                label.set_fontsize(16)
            if sz > 6:
                label.set_rotation(45)

        if "units" in kwargs:
            self.fig.text(
                0.99, 0.03, "data units :: %s" % (kwargs["units"],), ha="right"
            )

        title = kwargs.get("title")
        if title:
            self.ax.set_position(
                [
                    MAIN_AX_BOUNDS[0],
                    MAIN_AX_BOUNDS[1],
                    MAIN_AX_BOUNDS[2] - 0.03,
                    MAIN_AX_BOUNDS[3],
                ]
            )
            cb2.ax.text(
                -0.05,
                0.5,
                title,
                rotation=90,
                fontsize=16,
                transform=cb2.ax.transAxes,
                ha="right",
                va="center",
            )

    def plot_station(self, data, **kwargs):
        """Plot values on a map in a station plot like manner.

        Args:
          data (list): list of dicts with station data to plot
          fontsize (int): font size to use for plotted text
        """
        (x0, x1) = self.ax.set_xlim()
        # size to use for circles
        circlesz = (x1 - x0) / 180.0
        # (y0, y1) = self.ax.set_ylim()
        offsets = {
            1: [-4, 4, "right", "bottom"],
            2: [0, 4, "center", "bottom"],
            3: [4, 4, "left", "bottom"],
            4: [-4, 0, "right", "center"],
            5: [0, 0, "center", "center"],
            6: [4, 0, "left", "center"],
            7: [-4, -4, "right", "top"],
            8: [0, -4, "center", "top"],
            9: [4, -4, "left", "top"],
        }

        mask = np.zeros(self.fig.canvas.get_width_height(), bool)
        for stdata in data:
            (x, y) = self.ax.projection.transform_point(
                stdata["lon"], stdata["lat"], ccrs.Geodetic()
            )
            (imgx, imgy) = self.ax.transData.transform([x, y])
            imgx = int(imgx)
            imgy = int(imgy)
            # Check to see if this overlaps
            _cnt = np.sum(
                np.where(
                    mask[imgx - 15 : imgx + 15, imgy - 15 : imgy + 15], 1, 0
                )
            )
            if _cnt > 5:
                continue
            mask[imgx - 15 : imgx + 15, imgy - 15 : imgy + 15] = True
            # Plot bars
            if stdata.get("sknt") is not None and stdata["sknt"] > 1:
                (u, v) = wind_components(
                    units("knot") * stdata["sknt"],
                    units("degree") * stdata["drct"],
                )
                if u is not None and v is not None:
                    self.ax.barbs(x, y, u.m, v.m, zorder=Z_OVERLAY)

            # Sky Coverage
            skycoverage = stdata.get("coverage")
            if (
                skycoverage is not None
                and skycoverage >= 0
                and skycoverage <= 100
            ):
                w = Wedge(
                    (x, y), circlesz, 0, 360, ec="k", fc="white", zorder=2
                )
                self.ax.add_artist(w)
                w = Wedge(
                    (x, y),
                    circlesz,
                    0,
                    360.0 * skycoverage / 100.0,
                    ec="k",
                    fc="k",
                    zorder=3,
                )
                self.ax.add_artist(w)

            # Temperature
            val = stdata.get("tmpf")
            if val is not None:
                (offx, offy, ha, va) = offsets[1]
                self.ax.annotate(
                    stdata.get("tmpf_format", "%.0f") % (val,),
                    xy=(x, y),
                    ha=ha,
                    va=va,
                    xytext=(offx, offy),
                    color=stdata.get("tmpf_color", "r"),
                    textcoords="offset points",
                    zorder=Z_OVERLAY + 2,
                    clip_on=True,
                    fontsize=kwargs.get("fontsize", 8),
                )
            # Dew Point
            val = stdata.get("dwpf")
            if val is not None:
                (offx, offy, ha, va) = offsets[7]
                self.ax.annotate(
                    stdata.get("dwpf_format", "%.0f") % (val,),
                    xy=(x, y),
                    ha=ha,
                    va=va,
                    xytext=(offx, offy),
                    color=stdata.get("dwpf_color", "b"),
                    textcoords="offset points",
                    zorder=Z_OVERLAY + 2,
                    clip_on=True,
                    fontsize=kwargs.get("fontsize", 8),
                )
            # Plot identifier
            val = stdata.get("id")
            if val is not None:
                (offx, offy, ha, va) = (
                    offsets[6] if skycoverage is not None else offsets[5]
                )
                self.ax.annotate(
                    "%s" % (val,),
                    xy=(x, y),
                    ha=ha,
                    va=va,
                    xytext=(offx, offy),
                    color=stdata.get("id_color", "tan"),
                    textcoords="offset points",
                    zorder=Z_OVERLAY + 2,
                    clip_on=True,
                    fontsize=kwargs.get("fontsize", 8),
                )

    def plot_values(
        self,
        lons,
        lats,
        vals,
        fmt="%s",
        valmask=None,
        color="#000000",
        textsize=14,
        labels=None,
        labeltextsize=10,
        labelcolor="#000000",
        showmarker=False,
        labelbuffer=25,
        outlinecolor="#FFFFFF",
        zorder=None,
        **kwargs,
    ):
        """Plot values onto the map

        Args:
          lons (list): longitude values to use for placing `vals`
          lats (list): latitude values to use for placing `vals`
          vals (list): actual values to place on the map
          fmt (str, optional): Format specification to use for representing the
            values. For example, the default is '%s'.
          valmask (list, optional): Boolean list to use as masking of the
            `vals` while adding to the map.
          color (str, list, optional): Color to use while plotting the `vals`.
            This can be a list to specify each color to use with each value.
          textsize (str, optional): Font size to draw text.
            labels (list, optional): Optional list of labels to place below the
            plotting of `vals`
          labeltextsize (int, optional): Size of the label text
          labelcolor (str, optional): Color to use for drawing labels
          showmarker (bool, optional): Place a marker on the map for the label
          labelbuffer (int): pixel buffer around labels, a value of `0`
            disables the label culling logic.
          outlinecolor (color): color to use for text outlines
          zorder (int or list, optional): zorder to use for plotting.
          textoutlinewidth (int): width of the font outline, default 3.
        """
        if valmask is None:
            valmask = [True] * len(lons)
        if labels is None:
            labels = [""] * len(lons)
        if zorder is None:
            zorder = [Z_OVERLAY + 2] * len(lons)
        if isinstance(color, str):
            color = [color] * len(lons)
        bbox = self.fig.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted()
        )
        axbbox = self.ax.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted()
        )
        axx0 = axbbox.x0 * self.fig.dpi
        axx1 = (axbbox.x0 + axbbox.width) * self.fig.dpi
        axy0 = axbbox.y0 * self.fig.dpi
        axy1 = (axbbox.y0 + axbbox.height) * self.fig.dpi
        figwidth = bbox.width * self.fig.dpi
        figheight = bbox.height * self.fig.dpi
        if self.textmask is None:
            # zorder is used to track plotting priorities
            self.textmask = np.zeros((int(figwidth), int(figheight)), np.int8)
        # Create a fake label, to test out our scaling
        t0 = self.fig.text(
            0.5,
            0.5,
            "ABCDEFGHIJ",
            transform=self.ax.transAxes,
            color="None",
            size=textsize,
        )
        bbox = t0.get_window_extent(self.fig.canvas.get_renderer())
        xpixels_per_char = bbox.width / 10.0
        ypixels = bbox.height

        def _find_ax(lon, lat):
            """Figure out whom this point belongs."""
            for ax in self.axes:
                (x0, x1, y0, y1) = ax.get_extent()
                (x, y) = ax.projection.transform_point(
                    lon, lat, ccrs.Geodetic()
                )
                if (x0 <= x <= x1) and (y0 <= y <= y1):
                    return ax

        for o, a, v, m, c, label, z in zip(
            lons, lats, vals, valmask, color, labels, zorder
        ):
            if not m:
                continue

            ha = "center"
            mystr = fmt % (v,)
            max_mystr_len = max([len(s) for s in mystr.split("\n")])
            mystr_lines = len(mystr.split("\n"))
            # compute the pixel coordinate of this data point
            ax = _find_ax(o, a)
            if ax is None:
                continue
            (x, y) = ax.projection.transform_point(o, a, ccrs.Geodetic())
            (imgx, imgy) = ax.transData.transform([x, y])
            imgx0 = int(imgx - (max_mystr_len * xpixels_per_char / 2.0))
            if imgx0 < axx0:
                ha = "left"
                imgx0 = imgx
            imgx1 = imgx0 + max_mystr_len * xpixels_per_char
            if imgx1 > axx1:
                imgx1 = imgx
                imgx0 = imgx1 - max_mystr_len * xpixels_per_char
                ha = "right"
            # Now we buffer
            imgx0 = max([0, imgx0 - labelbuffer])
            imgx1 = min(
                [
                    figwidth,
                    (
                        imgx0
                        + 2 * labelbuffer
                        + max_mystr_len * xpixels_per_char
                    ),
                ]
            )
            imgy0 = max([0, int(imgy) - labelbuffer * 0.75])
            imgy1 = min(
                [
                    figheight,
                    (imgy0 + mystr_lines * ypixels + 2 * labelbuffer * 0.75),
                ]
            )
            overlap = (
                self.textmask[int(imgx0) : int(imgx1), int(imgy0) : int(imgy1)]
                >= z
            )
            _cnt = np.sum(overlap)
            # If we have more than 15 pixels of overlap, don't plot this!
            if _cnt > 15 and labelbuffer > 0:
                if self.debug:
                    LOG.info(
                        "culling |%s| due to overlap, %s", repr(mystr), _cnt
                    )
                continue
            if self.debug:
                rec = plt.Rectangle(
                    [imgx0, imgy0],
                    (imgx1 - imgx0),
                    (imgy1 - imgy0),
                    facecolor="None",
                    edgecolor="r",
                )
                self.fig.patches.append(rec)
            # Useful for debugging this algo
            if self.debug:
                LOG.info(
                    (
                        "label: %s imgx: %s/%s-%s imgy: %s/%s-%s "
                        "x:%s-%s y:%s-%s _cnt:%s"
                    ),
                    repr(mystr),
                    imgx,
                    axx0,
                    axx1,
                    imgy,
                    axy0,
                    axy1,
                    imgx0,
                    imgx1,
                    imgy0,
                    imgy1,
                    _cnt,
                )
            self.textmask[
                int(imgx0) : int(imgx1), int(imgy0) : int(imgy1)
            ] = np.where(
                self.textmask[int(imgx0) : int(imgx1), int(imgy0) : int(imgy1)]
                < z,
                z,
                self.textmask[
                    int(imgx0) : int(imgx1), int(imgy0) : int(imgy1)
                ],
            )
            t0 = ax.text(
                o,
                a,
                mystr,
                color=c,
                size=textsize,
                zorder=z,
                va="center" if not showmarker else "bottom",
                ha=ha,
                transform=ccrs.PlateCarree(),
            )
            bbox = t0.get_window_extent(self.fig.canvas.get_renderer())
            if self.debug:
                rec = plt.Rectangle(
                    [bbox.x0, bbox.y0],
                    bbox.width,
                    bbox.height,
                    facecolor="None",
                    edgecolor="k",
                )
                self.fig.patches.append(rec)
            if showmarker:
                ax.scatter(
                    o,
                    a,
                    marker="+",
                    zorder=z,
                    color="k",
                    transform=ccrs.PlateCarree(),
                )
            t0.set_clip_on(True)
            t0.set_path_effects(
                [
                    PathEffects.Stroke(
                        linewidth=kwargs.get("textoutlinewidth", 3),
                        foreground=outlinecolor,
                    ),
                    PathEffects.Normal(),
                ]
            )

            if label and label != "":
                ax.annotate(
                    "%s" % (label,),
                    xy=(x, y),
                    ha="center",
                    va="top",
                    xytext=(0, 0 - textsize / 2),
                    color=labelcolor,
                    textcoords="offset points",
                    zorder=z - 1,
                    clip_on=True,
                    fontsize=labeltextsize,
                )

    def scatter(self, lons, lats, vals, clevs, **kwargs):
        """Draw points on the map

        Args:
          lons (list): longitude values
          lats (list): latitude values
          vals (list): Data values for the points to use for colormapping
          clevs (list): Levels to use for ramp
          **kwargs: additional options
        """
        cmap = stretch_cmap(
            kwargs.get("cmap"), clevs, extend=kwargs.get("extend")
        )
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        colors = cmap(norm(vals))
        self.ax.scatter(
            lons,
            lats,
            c=colors,
            edgecolors=colors,
            transform=ccrs.PlateCarree(),
            zorder=Z_OVERLAY,
        )
        kwargs.pop("cmap", None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)

    def hexbin(self, lons, lats, vals, clevs, **kwargs):
        """ hexbin wrapper """
        cmap = stretch_cmap(
            kwargs.get("cmap"), clevs, extend=kwargs.get("extend")
        )
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        points = self.ax.projection.transform_points(
            ccrs.PlateCarree(), lons, lats
        )
        _hex = self.ax.hexbin(
            points[:, 0],
            points[:, 1],
            C=vals,
            norm=norm,
            cmap=cmap,
            zorder=Z_FILL,
        )
        kwargs.pop("cmap", None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return _hex

    def pcolormesh(self, lons, lats, vals, clevs, **kwargs):
        """Opinionated mpl.pcolormesh wrapper.

        If you supply a lons in the same shape of the vals, this method will
        tack on an extra row and column to make matplotlib happy. If you do
        not want this, then pass your own lons + lats that is 1 column and 1
        row greater than vals.
        """
        cmap = stretch_cmap(
            kwargs.get("cmap"), clevs, extend=kwargs.get("extend")
        )
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        if lons.shape == vals.shape:
            # Tack on some extra
            new = lons[-1, :] * 2 - lons[-2, :]
            lons = np.r_[lons, [new]]
            new = lats[-1, :] * 2 - lats[-2, :]
            lats = np.r_[lats, [new]]
            new = lons[:, -1] * 2 - lons[:, -2]
            lons = np.c_[lons, new]
            new = lats[:, -1] * 2 - lats[:, -2]
            lats = np.c_[lats, new]

        res = self.ax.pcolormesh(
            lons,
            lats,
            vals,
            norm=norm,
            cmap=cmap,
            zorder=Z_FILL,
            transform=ccrs.PlateCarree(),
        )

        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop("cmap", None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return res

    def draw_mask(self, sector=None):
        """Draw a mask on the main axes.

        If `sector` is not provided, this attempts to intelligently to the
        masking the user wants.

        Args:
          sector (str,optional): Hard code what type of sector masking should
            happen.
        """
        sector = self.sector if sector is None else sector
        # can't mask what we don't have a polygon bounds for.
        if sector not in (
            "iailin",
            "midwest",
            "conus",
            "state",
            "iowawfo",
            "cwa",
        ):
            return
        # in lon,lat
        if sector == "state":
            s = load_geodf("us_states")
            mask_outside_geom(self.ax, s.at[self.state, "geom"])
            return
        if sector == "cwa":
            s = load_geodf("cwa")
            mask_outside_geom(self.ax, s.at[self.cwa, "geom"])
            return
        if sector == "conus":
            s = load_geodf("conus")
            mask_outside_geom(self.ax, s.iloc[0]["geom"])
            return
        if sector == "iowawfo":
            s = load_geodf("iowawfo")
            geo = s["geom"].values[0]
            ccw = np.asarray(geo.exterior)[::-1]
        else:
            ccw = load_bounds("%s_ccw" % (sector,))
        # in map coords
        points = self.ax.projection.transform_points(
            ccrs.Geodetic(), ccw[:, 0], ccw[:, 1]
        )
        mask_outside_polygon(points[:, :2], ax=self.ax)

    def contourf(self, lons, lats, vals, clevs, **kwargs):
        """Contourf

        Args:
          ilabel (boolean,optional): Should we label contours
          iline (boolean,optional): should we draw contour lines

        Returns:
          vals (np.array): The values used for plotting, maybe after gridding
        """
        if isinstance(lons, list):
            lons = np.array(lons)
            lats = np.array(lats)
            vals = np.array(vals)
        if np.array(vals).ndim == 1:
            # We need to grid, get current plot bounds in display proj
            # Careful here as a rotated projection may have maxes not in ul
            xbnds = self.ax.get_xlim()
            ybnds = self.ax.get_ylim()
            ll = ccrs.Geodetic().transform_point(
                xbnds[0], ybnds[0], self.ax.projection
            )
            cl = ccrs.Geodetic().transform_point(
                xbnds[0], sum(ybnds) / 2, self.ax.projection
            )
            ul = ccrs.Geodetic().transform_point(
                xbnds[0], ybnds[1], self.ax.projection
            )
            uc = ccrs.Geodetic().transform_point(
                sum(xbnds) / 2, ybnds[1], self.ax.projection
            )
            ur = ccrs.Geodetic().transform_point(
                xbnds[1], ybnds[1], self.ax.projection
            )
            cr = ccrs.Geodetic().transform_point(
                xbnds[1], sum(ybnds) / 2, self.ax.projection
            )
            lr = ccrs.Geodetic().transform_point(
                xbnds[1], ybnds[0], self.ax.projection
            )
            lc = ccrs.Geodetic().transform_point(
                sum(xbnds) / 2, ybnds[0], self.ax.projection
            )
            xi = np.linspace(
                min(ll[0], cl[0], ul[0]),
                max(lr[0], cr[0], ur[0]),
                100,
            )
            yi = np.linspace(
                min(ll[1], lc[1], lr[1]),
                max(ul[1], uc[1], ur[1]),
                100,
            )
            xi, yi = np.meshgrid(xi, yi)
            nn = NearestNDInterpolator((lons, lats), vals)
            vals = nn(xi, yi)
            lons = xi
            lats = yi
            window = np.ones((6, 6))
            vals = convolve2d(
                vals, window / window.sum(), mode="same", boundary="symm"
            )
        if lons.ndim == 1:
            lons, lats = np.meshgrid(lons, lats)

        cmap = stretch_cmap(
            kwargs.get("cmap"), clevs, extend=kwargs.get("extend")
        )
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        # vals = maskoceans(lons, lats, vals, resolution='h')
        self.ax.contourf(
            lons,
            lats,
            vals,
            clevs,
            cmap=cmap,
            norm=norm,
            zorder=Z_FILL,
            extend="both",
            transform=ccrs.PlateCarree(),
        )
        if kwargs.get("iline", True):
            csl = self.ax.contour(
                lons,
                lats,
                vals,
                clevs,
                colors="w",
                zorder=Z_FILL_LABEL,
                transform=ccrs.PlateCarree(),
            )
            if kwargs.get("ilabel", False):
                self.ax.clabel(
                    csl,
                    fmt=kwargs.get("labelfmt", "%.0f"),
                    colors="k",
                    fontsize=14,
                )
        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop("cmap", None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return vals

    def fill_climdiv(self, data, **kwargs):
        """Fill climate divisions using provided data dictionary

        Args:
          data (dict): A dictionary of climate division IDs and values
        """
        geodf = load_geodf("climdiv")
        polygon_fill(self, geodf, data, **kwargs)

    def fill_ugcs(self, data, **kwargs):
        """Overlay filled UGC geometries

        Note the importance of the `is_firewx` flag.  This determines which
        UGC database to look at in the face of ambiquity.

        Args:
          data(dict): A dictionary of 6 char UGC code keys and values
          bins(list, optional): Bins to use for cloropleth, default 0:101:10
          color(dict, optional): Hard code what each UGC should display as
            for color.
          is_firewx(bool, optional): Are we plotting fire weather zones?
          nocbar (bool, optional): Should a color bar be generated, default is
            `True`.
          plotmissing(bool, optional): Should missing UGC data be plotted?
          labels(dict, optional): UGC indexed dictionary to use for labeling.
          missingval(str, optional): value to use when labelling UGCs with
            missing values, defaults to '-'.
        """
        # Figure out if we have zones or counties/parishes
        counties = True
        for key in data:
            if key[2] == "Z":
                counties = False
            break
        zonesfn = "firewx" if kwargs.get("is_firewx", False) else "zone"
        geodf = load_geodf("ugcs_county" if counties else f"ugcs_{zonesfn}")
        if self.sector == "state":
            geodf = geodf[geodf.index.str.slice(0, 2) == self.state]
        elif self.sector == "cwa":
            geodf = geodf[geodf["cwa"] == self.cwa]
        polygon_fill(self, geodf, data, **kwargs)

    def fill_states(self, data, **kwargs):
        """Add overlay of filled state polygons"""
        geodf = load_geodf("us_states")
        polygon_fill(self, geodf, data, **kwargs)

    def draw_cwas(self, color="k", **kwargs):
        """Overlay CWA Borders

        Draw the CWA border lines on the map.

        Args:
          color(str): The color to draw the CWA borders with
          kwargs(dict, optional): Parameters passed to matplotlib for plotting
        """
        kwargs["edgecolor"] = color
        cwas = load_geodf("cwa")
        for _a in self.axes:
            _a.add_geometries(
                cwas["geom"].values,
                crs=ccrs.PlateCarree(),
                zorder=Z_POLITICAL,
                facecolor="None",
                **kwargs,
            )

    def fill_cwas(self, data, **kwargs):
        """Add overlay of filled polygons for NWS Forecast Offices.

        Method adds a colorized overlay of NWS Forecast Offices based on a
        data dictionary of values provided. This method also places a color
        bar on the image.

        Args:
          data (dict): Dictionary of values with keys representing the 3 char
            or 4 char idenitifer for the WFO.  This assumes the 3 char sites
            are the K ones.
        """
        geodf = load_geodf("cwa")
        # Painfull.  San Juan's WFO identifier is SJU, but VTEC uses JSJ, our
        # plotting here uses SJU
        if "JSJ" in data:
            data["SJU"] = data["JSJ"]
        polygon_fill(self, geodf, data, **kwargs)

    def drawcities(self, **kwargs):
        """Overlay some cities

        Args:
          minarea (int,optional): Minimum Urban Area size (km2) to plot
          labelbuffer (int): approximate number of pixels to compute overlap
          textsize (int): size of the text
          color (str): color to plot the text with
          outlinecolor (str): color to outline the text with
        """
        df = load_pickle_pd("pd_cities.pickle")
        (west, east, south, north) = self.ax.get_extent(crs=ccrs.PlateCarree())

        minarea = kwargs.get(
            "minarea", 500.0 if self.sector in ["nws", "conus"] else 10.0
        )
        df2 = df[
            (
                (df["lat"] > south)
                & (df["lat"] < north)
                & (df["lon"] > west)
                & (df["lon"] < east)
                & (df["area_km2"] > minarea)
            )
        ]
        # debug option to test an individual point on the plot
        # df2 = df[(df['name'] == 'Sioux City')]
        # hack around a API break
        tsz = kwargs.pop("textsize", 16)
        self.plot_values(
            df2.lon.values,
            df2.lat.values,
            df2.name.values,
            showmarker=True,
            textsize=tsz,
            **kwargs,
        )

    def drawcounties(self, color="k"):
        """Draw counties onto the map

        Args:
          color (color,optional): line color to use
        """
        geodf = load_geodf("ugcs_county")
        self.ax.add_geometries(
            geodf["geom"].values,
            crs=ccrs.PlateCarree(),
            facecolor="None",
            edgecolor=color,
            lw=0.4,
            zorder=Z_POLITICAL,
        )

    def postprocess(self, **kwargs):
        """Postprocessing.

        Args:
          filename (str): file to save output to.
          web (bool): Write result to sys.stdout, default False.
          memcache (obj): write image to memcache
          memcachekey (str): key to use when writing to memcache.
          memcacheexpire (int): how long should we persist in memcache,
            default is 300.
          pqstr (str): Do pqinsert with the following LDM product name.
        """
        ram = BytesIO()
        self.fig.savefig(ram, format="png")
        ram.seek(0)
        im = Image.open(ram)
        im2 = im.convert("RGB").convert("P", palette=Image.ADAPTIVE)
        if kwargs.get("memcache") and kwargs.get("memcachekey"):
            ram = BytesIO()
            im2.save(ram, format="png")
            ram.seek(0)
            r = ram.read()
            kwargs["memcache"].set(
                kwargs["memcachekey"],
                r,
                time=kwargs.get("memcacheexpire", 300),
            )
        if kwargs.get("web", False):
            ssw("Content-Type: image/png\n\n")
            im2.save(getattr(sys.stdout, "buffer", sys.stdout), format="png")
            return
        tmpfd = tempfile.NamedTemporaryFile(delete=False)
        im2.save(tmpfd, format="PNG")
        tmpfd.close()
        if kwargs.get("pqstr") is not None:
            subprocess.call(
                "pqinsert -p '%s' %s" % (kwargs.get("pqstr"), tmpfd.name),
                shell=True,
            )
        if kwargs.get("filename") is not None:
            shutil.copyfile(tmpfd.name, kwargs.get("filename"))
        os.unlink(tmpfd.name)

    def overlay_roadcond(self, valid=None):
        """Overlay Iowa Winter Road Conditions.

        Args:
          valid (datetime.datetime): Valid time for NEXRAD overlay.
        """
        if valid is None:
            valid = utc()
        if hasattr(valid, "tzinfo"):
            valid = valid.astimezone(datetime.timezone.utc)
        url = (
            "https://mesonet.agron.iastate.edu/"
            "api/1/iowa_winter_roadcond.geojson"
        )
        tstamp = valid.strftime("%Y-%m-%d %H:%M")
        try:
            req = requests.get(url, params={"valid": tstamp}, timeout=30)
        except requests.ConnectionError as exp:
            warnings.warn("overlay_roadcond failed: %s" % (exp,))
            return None
        df = gpd.GeoDataFrame().from_features(req.json())
        labels = []
        for _, row in df.iterrows():
            for geo in row["geometry"]:
                self.ax.plot(
                    *geo.xy,
                    transform=ccrs.PlateCarree(),
                    color=row["color"],
                    linewidth=2 if row["rtype"] > 1 else 4,
                    zorder=Z_OVERLAY2,
                    label=None if row["label"] in labels else row["label"],
                )
                if row["label"] not in labels:
                    labels.append(row["label"])
        self.ax.legend(
            loc=3,
            ncol=6,
            fontsize=10,
            facecolor="white",
            framealpha=1,
        ).set_zorder(Z_OVERLAY2 + 5)

    def overlay_nexrad(self, valid=None, product="N0Q"):
        """Overlay an IEM NEXRAD Composite Image.

        Args:
          valid (datetime.datetime): Valid time for NEXRAD overlay.
          product (str): either N0Q or N0R for the mosaic type.

        Returns:
          valid time of the NEXRAD, or None if not found.
        """
        if valid is None:
            valid = utc()
        if hasattr(valid, "tzinfo"):
            valid = valid.astimezone(datetime.timezone.utc)
        if product not in ["N0R", "N0Q"]:
            raise ValueError("nexrad `product` not in {N0R,N0Q}")
        # Rectify to modulus 5 minutes
        valid -= datetime.timedelta(minutes=(valid.minute % 5))
        compsector = "us"
        if self.sector == "state" and self.state in ["AK", "HI", "PR"]:
            compsector = self.state.lower()
        elif self.sector == "cwa" and self.cwa in ["AFG", "AJK", "AFC"]:
            compsector = "ak"
        elif self.sector == "cwa" and self.cwa in [
            "HFO",
        ]:
            compsector = "hi"
        elif self.sector == "cwa" and self.cwa in [
            "SJU",
        ]:
            compsector = "pr"
        baseurl = valid.strftime(
            "https://mesonet.agron.iastate.edu/archive/data/%Y/%m/%d/"
            f"GIS/{compsector}comp/{product.lower()}_%Y%m%d%H%M."
        )
        req_png = exponential_backoff(
            requests.get, baseurl + "png", timeout=10
        )
        req_wld = exponential_backoff(
            requests.get, baseurl + "wld", timeout=10
        )
        if req_png is None or req_png.status_code != 200:
            LOG.debug("Failed to fetch %spng", baseurl)
            return None
        if req_wld is None or req_wld.status_code != 200:
            LOG.debug("Failed to fetch %swld", baseurl)
            return None
        (dx, _, _, dy, west, north) = [
            float(x) for x in req_wld.content.decode("ascii").split("\n")
        ]
        bio = BytesIO(req_png.content)
        bio.seek(0)
        im = np.asarray(Image.open(bio))
        # Use rasterio to reproject this grid into the projection of axes
        with rasterio.Env():
            src_aff = rasterio.Affine(dx, 0, west, 0, dy, north)
            src_crs = {"init": "EPSG:4326"}
            (px0, px1, py0, py1) = self.ax.get_extent()
            pbbox = self.ax.get_window_extent()
            pdx = (px1 - px0) / pbbox.width
            pdy = (py1 - py0) / pbbox.height
            dest_aff = rasterio.Affine(pdx, 0, px0, 0, pdy, py0)
            res = np.zeros(
                (int(pbbox.height), int(pbbox.width)), dtype=im.dtype
            )
            reproject(
                im,
                res,
                src_transform=src_aff,
                src_crs=src_crs,
                src_nodata=0,
                dst_transform=dest_aff,
                dst_crs=self.ax.projection.proj4_params,
                resampling=Resampling.nearest,
            )

        ramp = pd.read_csv(f"{DATADIR}/ramps/composite_{product.lower()}.txt")
        cmap = mpcolors.ListedColormap(ramp[["r", "g", "b"]].to_numpy() / 256)
        cmap.set_under((0, 0, 0, 0))
        norm = mpcolors.BoundaryNorm(ramp["coloridx"].values, cmap.N)
        self.ax.imshow(
            res,
            interpolation="nearest",  # prevents artifacts
            extent=(px0, px1, py0, py1),
            cmap=cmap,
            norm=norm,
            zorder=Z_FILL,
            origin="lower",
        ).set_rasterized(True)
        pos = self.ax.get_position()
        cax = self.fig.add_axes([pos.x1 - 0.35, pos.y1 - 0.01, 0.35, 0.015])
        cb = mpcolorbar.ColorbarBase(
            cax,
            cmap=cmap,
            norm=norm,
            ticks=ramp.loc[ramp["value"] % 20 == 0]["coloridx"].values,
            extend="neither",
            orientation="horizontal",
            drawedges=False,
            ticklocation="top",
        )
        cb.set_ticklabels(
            [
                "%.0d" % (d,)
                for d in ramp.loc[ramp["value"] % 20 == 0]["value"].values
            ]
        )
        self.fig.text(pos.x1, pos.y1 + 0.005, "dBZ", ha="left")
        return valid


def windrose(*args, **kwargs):
    """Depreciated."""
    warnings.warn(
        "windrose() is depreciated, use pyiem.windrose_utils!",
        DeprecationWarning,
    )
    import pyiem.windrose_utils as wru

    return wru.windrose(*args, **kwargs)