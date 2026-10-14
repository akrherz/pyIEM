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

import os
import shutil
import subprocess
import sys
import tempfile
import warnings
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

import geopandas as gpd
import matplotlib.cm as mpcm
import matplotlib.colors as mpcolors
import matplotlib.patheffects as PathEffects
import numpy as np
import pandas as pd
import rasterio
import requests
from affine import Affine
from matplotlib.patches import Rectangle, Wedge
from matplotlib.transforms import Bbox
from metpy.calc import wind_components
from metpy.units import units
from PIL import Image
from rasterio.warp import Resampling, reproject
from scipy.interpolate import NearestNDInterpolator
from scipy.signal import convolve2d
from shapely.geometry import shape

from pyiem.plot.colormaps import radar_ptype, stretch_cmap
from pyiem.plot.textcollider import TextCollider
from pyiem.plot.use_agg import figure
from pyiem.plot.util import (
    draw_features_from_shapefile,
    draw_logo,
    fitbox,
    mask_outside_geom,
    mask_outside_polygon,
    polygon_fill,
    ramp2df,
    sector_setter,
    update_kwargs_apctx,
)
from pyiem.reference import (
    FIGSIZES,
    LATLON,
    TWITTER_RESOLUTION_INCH,
    Z_CF,
    Z_CLIP,  # noqa
    Z_CLIP2,  # noqa
    Z_FILL,
    Z_FILL_LABEL,
    Z_FRAME,  # noqa
    Z_OVERLAY,
    Z_OVERLAY2,
    Z_POLITICAL,
)
from pyiem.util import LOG, load_geodf, ssw, utc

# geopandas currently emits this as parquet is unstable.
warnings.filterwarnings("ignore", message=".*implementation of Parquet.*")


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
    fn = os.path.join(DATADIR, f"{filebase}.npy")
    if not os.path.isfile(fn):
        LOG.warning("load_bounds(%s) is missing!", fn)
        return None
    return np.load(fn)


class MapPlot:
    """An object representing a matplotlib figure.

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

    @update_kwargs_apctx
    def __init__(self, sector="iowa", **kwargs):
        """Construct a MapPlot

        Args:
          sector (str): plot domain, set 'custom' to bring your own bounds.
          kwargs:
            crs (pyproj.crs,optional): bring your own crs
            north (float,optional): Plot top bounds (degN Lat)
            south (float,optional): Plot bottom bounds (degN Lat)
            east (float,optional): Plot right bounds (degE Lon)
            west (float,optional): Plot left bounds (degE Lon)
            titlefontsize (int): fontsize to use for the plot title
            subtitlefontsize (int): fontsize to use for the plot subtitle
            continentalcolor (color): color to use for continental coloring
            debug (bool): enable debugging
            aspect (str): plot aspect, defaults to auto
            fig (matplotlib.figure.Figure,optional): provide a figure instance
              for more advanced plot control.
            logo (str,optional): logo name to slap on the plot.
            twitter (bool): Set an image resolution that is favorable to
              posting to Twitter. Default: False.
            apctx (dict,optional): dict of autoplot content
            axes_position (list,optional): list of
              [left, bottom, width, height] for the main axes.
            stateborderwidth (float,optional): how wide to make the
              state borders (default: 1.).
            background (str,optional): Background imagery to use `ne2` is the
              only option currently.
        """
        self.debug = kwargs.get("debug", False)
        self.fig = kwargs.pop("fig", None)
        figsize = kwargs.get("figsize", FIGSIZES["43"])
        if kwargs.get("twitter", False) is True:
            figsize = TWITTER_RESOLUTION_INCH
        if self.fig is None:
            self.fig = figure(figsize=figsize, dpi=kwargs.get("dpi", 100))
        # Storage of axes within this plot
        self.state = None
        self.cwa = None
        self.fema_region = None
        self.textcollider = None  # plot_values label collision tracking
        self.sector = sector
        self.cax = self.fig.add_axes(
            CAX_BOUNDS, frameon=False, yticks=[], xticks=[]
        )
        self.panels = []
        self.ax = None  # Main plot axes, will be set later, hacky
        # hack around sector=iowa
        if self.sector == "iowa":
            self.sector = "state"
            self.state = "IA"
        axes_position = kwargs.pop("axes_position", MAIN_AX_BOUNDS)
        sector_setter(self, axes_position, **kwargs)
        has_background = kwargs.get("background") is not None
        for gp in self.panels:
            # legacy usage of axisbg here
            _c = kwargs.get(
                "axisbg", kwargs.get("continentalcolor", "#EEEEEE")
            )
            if not has_background:
                draw_features_from_shapefile(
                    gp, "land", facecolor=_c, zorder=Z_CF
                )
            # NB we neeed both borders (lines between countries) and
            # coastlines (lines between land and water)
            draw_features_from_shapefile(
                gp,
                "borders",
                lw=1.0,
                ec="k",
                zorder=Z_POLITICAL,
            )
            draw_features_from_shapefile(
                gp,
                "coastline",
                lw=1.0,
                ec="k",
                zorder=Z_POLITICAL,
            )
            if not has_background:
                draw_features_from_shapefile(
                    gp,
                    "lakes",
                    edgecolor=(0.4471, 0.6235, 0.8117),
                    facecolor=(0.4471, 0.6235, 0.8117),
                    zorder=Z_CF,
                )
            if "nostates" not in kwargs:
                xlim = gp.ax.get_xlim()
                ylim = gp.ax.get_ylim()
                # NB using clip here was trouble with geos
                _df = (
                    load_geodf("us_states", gp.crs.to_epsg())
                    .to_crs(gp.crs)
                    .cx[slice(*gp.get_xlim()), slice(*gp.get_ylim())]
                )
                if not _df.empty:
                    _df.plot(
                        ax=gp.ax,
                        aspect=None,
                        lw=kwargs.get("stateborderwidth", 1.0),
                        edgecolor=kwargs.get("statebordercolor", "k"),
                        facecolor="None",
                        zorder=Z_OVERLAY + 2,
                        add_labels=False,
                    )
                gp.ax.set_xlim(xlim)
                gp.ax.set_ylim(ylim)

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
                f"{kwargs.get('caption', 'Iowa Environmental Mesonet')} :: "
                f"generated {datetime.now():%d %B %Y %I:%M %p %Z}",
            )

    def close(self):
        """Close the figure in the case of batch processing"""
        # this is ugly, but it seems effective
        del self.fig

    def draw_usdm(
        self, valid=None, filled=True, hatched=False, **kwargs
    ) -> date | None:
        """Overlay the US Drought Monitor

        This utilizes a GeoJSON web service provided by the IEM.  The provided
        date to this method is passed to the web service which rectifies the
        date to provide the USDM analysis valid for that date.  If no date
        is specified, the current analysis is plotted.

        Args:
          valid (str or datetime.date): The valid time to plot this USDM
          filled (boolean): Should we draw lines or filled polygons
          hatched (boolean): Should we use hatch filling
          alpha (float): Alpha value for the polygons, default 0.5.

        Return:
          date that the USDM is valid for
        """
        colors = ["#ffff00", "#fcd37f", "#ffaa00", "#e60000", "#730000"]
        hatches = ["+", "/", "\\", "-", "x"]
        params = {}
        if isinstance(valid, (date, datetime)):
            valid = valid.strftime("%Y-%m-%d")
            params["date"] = valid
        url = "http://mesonet.agron.iastate.edu/geojson/usdm.py"
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            df = gpd.GeoDataFrame().from_features(resp.json())
        except Exception as exp:
            warnings.warn(
                f"draw_usdm IEM USDM Webservice failed: {exp}", stacklevel=1
            )
            return None
        lw = 1 if filled else 4.0
        usdm_valid = df.iloc[0]["date"]
        alpha = kwargs.pop("alpha", 0.5)
        for _, row in df.iterrows():
            color = colors[row["dm"]]
            geom = shape(row["geometry"])
            fc = color if filled else "None"
            ec = color if not filled else "k"
            self.panels[0].add_geometries(
                [geom],
                LATLON,
                facecolor="None",
                edgecolor=ec,
                linewidth=lw,
                zorder=Z_OVERLAY2,
            )
            if filled:
                self.panels[0].add_geometries(
                    [geom],
                    LATLON,
                    facecolor=fc,
                    alpha=alpha,
                    edgecolor="None",
                    zorder=Z_OVERLAY,
                )
            elif hatched:
                self.panels[0].add_geometries(
                    [geom],
                    LATLON,
                    facecolor="None",
                    hatch=hatches[row["dm"]],
                    edgecolor=color,
                    zorder=Z_OVERLAY2 + 2,
                )

        self.panels[0].ax.text(
            0.99,
            0.99,
            "D4",
            color="k",
            transform=self.panels[0].ax.transAxes,
            va="top",
            ha="right",
            bbox=dict(color=colors[4]),
            zorder=Z_OVERLAY2 + 3,
        )
        self.panels[0].ax.text(
            0.955,
            0.99,
            "D3",
            color="k",
            transform=self.panels[0].ax.transAxes,
            va="top",
            ha="right",
            bbox=dict(color=colors[3]),
            zorder=Z_OVERLAY2 + 3,
        )
        self.panels[0].ax.text(
            0.92,
            0.99,
            "D2",
            color="k",
            transform=self.panels[0].ax.transAxes,
            va="top",
            ha="right",
            bbox=dict(color=colors[2]),
            zorder=Z_OVERLAY2 + 3,
        )
        self.panels[0].ax.text(
            0.885,
            0.99,
            "D1",
            color="k",
            transform=self.panels[0].ax.transAxes,
            va="top",
            ha="right",
            bbox=dict(color=colors[1]),
            zorder=Z_OVERLAY2 + 3,
        )
        self.panels[0].ax.text(
            0.85,
            0.99,
            "D0",
            color="k",
            transform=self.panels[0].ax.transAxes,
            va="top",
            ha="right",
            bbox=dict(color=colors[0]),
            zorder=Z_OVERLAY2 + 3,
        )
        self.panels[0].ax.text(
            0.815,
            0.99,
            f"USDM {usdm_valid}",
            color="w",
            transform=self.panels[0].ax.transAxes,
            va="top",
            ha="right",
            bbox=dict(color="k"),
            zorder=Z_OVERLAY2 + 3,
        )
        return datetime.strptime(usdm_valid, "%Y-%m-%d")

    def draw_radar_ptype_legend(self):
        """Draw a legend for radar precipitation type."""
        ramps = radar_ptype()
        pos = self.cax.get_position()
        w75 = pos.width * 0.75
        x0 = pos.x0 + 0.015
        axes = [
            self.fig.add_axes((x0, pos.y0, w75, pos.height / 5)),
            self.fig.add_axes(
                (x0, pos.y0 + pos.height / 4, w75, pos.height / 5)
            ),
            self.fig.add_axes(
                (x0, pos.y0 + pos.height / 2, w75, pos.height / 5)
            ),
            self.fig.add_axes(
                (x0, pos.y0 + pos.height * 0.75, w75, pos.height / 5)
            ),
        ]
        levels = np.arange(0, 55.1, 2.5)
        norm = mpcolors.BoundaryNorm(levels, 22)
        for i, (name, colors) in enumerate(ramps.items()):
            cmap = mpcolors.ListedColormap(colors, name=name)
            cb = self.fig.colorbar(
                mpcm.ScalarMappable(norm=norm, cmap=cmap),
                cax=axes[i],
                boundaries=levels,
                ticks=range(0, 51, 10),
                spacing="uniform",
                orientation="vertical",
            )
            # Remove minor ticks
            cb.ax.yaxis.set_tick_params(which="minor", width=0)
            cb.ax.text(
                -0.03,
                0.5,
                name if name != "icep" else "sleet",
                va="center",
                ha="right",
                rotation=90,
            )

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
        self.cax.set_frame_on(True)
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
        cb2 = self.fig.colorbar(
            mpcm.ScalarMappable(norm=norm, cmap=cmap),
            cax=self.cax,
            boundaries=blevels,
            extend=extend,
            ticks=clevs[stride],
            spacing=kwargs.get("spacing", "uniform"),
            orientation="vertical",
        )

        def _myrepr(val):
            """avoid list conversion in matplotlib that fowls numpy floats."""
            try:
                return f"{val:g}"
            except (TypeError, ValueError):
                return f"{val}"

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
                0.99, 0.03, f"data units :: {kwargs['units']}", ha="right"
            )

        title = kwargs.get("title")
        if title:
            pos = self.panels[0].ax.get_position()
            self.panels[0].ax.set_position(
                [
                    pos.x0,
                    pos.y0,
                    pos.width - 0.03,
                    pos.height,
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
        (x0, x1) = self.panels[0].ax.set_xlim()
        # size to use for circles
        circlesz = (x1 - x0) / 180.0
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

        ax = self.panels[0].ax
        fontsize = kwargs.get("fontsize", 8)
        # Each station claims a square of this half-width in pixels
        collider = TextCollider()
        half = 15

        def _annotate(text, xy, offset_key, color):
            offx, offy, ha, va = offsets[offset_key]
            ax.annotate(
                text,
                xy=xy,
                ha=ha,
                va=va,
                xytext=(offx, offy),
                color=color,
                textcoords="offset points",
                zorder=Z_OVERLAY + 2,
                clip_on=True,
                fontsize=fontsize,
            )

        for stdata in data:
            (x, y) = self.panels[0].transform_lonlat(
                stdata["lon"], stdata["lat"]
            )
            (imgx, imgy) = ax.transData.transform([x, y])
            if not collider.try_claim(
                (imgx - half, imgy - half, imgx + half, imgy + half), 0
            ):
                continue
            # Plot bars
            if stdata.get("sknt") is not None and stdata["sknt"] > 1:
                (u, v) = wind_components(
                    units("knot") * stdata["sknt"],
                    units("degree") * stdata["drct"],
                )
                if u is not None and v is not None:
                    ax.barbs(x, y, u.m, v.m, zorder=Z_OVERLAY)

            # Sky Coverage
            skycoverage = stdata.get("coverage")
            if skycoverage is not None and 0 <= skycoverage <= 100:
                ax.add_artist(
                    Wedge(
                        (x, y), circlesz, 0, 360, ec="k", fc="white", zorder=2
                    )
                )
                ax.add_artist(
                    Wedge(
                        (x, y),
                        circlesz,
                        0,
                        360.0 * skycoverage / 100.0,
                        ec="k",
                        fc="k",
                        zorder=3,
                    )
                )

            val = stdata.get("tmpf")
            if val is not None:
                _annotate(
                    stdata.get("tmpf_format", "%.0f") % (val,),
                    (x, y),
                    1,
                    stdata.get("tmpf_color", "r"),
                )
            val = stdata.get("dwpf")
            if val is not None:
                _annotate(
                    stdata.get("dwpf_format", "%.0f") % (val,),
                    (x, y),
                    7,
                    stdata.get("dwpf_color", "b"),
                )
            val = stdata.get("id")
            if val is not None:
                _annotate(
                    f"{val}",
                    (x, y),
                    6 if skycoverage is not None else 5,
                    stdata.get("id_color", "tan"),
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
        textoutlinewidth=3,
        isolated=False,
        backgroundcolor=None,
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
          textoutlinewidth (int): width of the font outline, default 3. A value
            <= 0 disables text outlines.
          isolated (bool): Only compute label collision against labels within
            this plot_values call. Default `false`
          backgroundcolor (color): color to use for the background of the label
            text, default is None.
        """
        if kwargs:
            warnings.warn(
                "plot_values ignoring unsupported keyword(s): "
                + ", ".join(sorted(kwargs)),
                stacklevel=2,
            )
        n = len(lons)
        valmask = np.ones(n, bool) if valmask is None else np.asarray(valmask)
        labels = [""] * n if labels is None else labels
        if zorder is None:
            zorder = Z_OVERLAY + 2
        if np.isscalar(zorder):
            zorder = [zorder] * n
        if isinstance(color, str):
            color = [color] * n
        if isolated:
            collider = TextCollider()
        else:
            if self.textcollider is None:
                self.textcollider = TextCollider()
            collider = self.textcollider
        # Create a geodataframe to use for clipping
        gdf = gpd.GeoDataFrame(
            {
                "geometry": gpd.points_from_xy(lons, lats, crs=LATLON),
                "val": vals,
                "color": color,
                "backgroundcolor": backgroundcolor,
                "label": labels,
                "zorder": zorder,
            }
        )
        gdf = gdf[valmask.astype(bool)]
        style = {
            "fmt": fmt,
            "textsize": textsize,
            "labeltextsize": labeltextsize,
            "labelcolor": labelcolor,
            "showmarker": showmarker,
            "labelbuffer": labelbuffer,
            "outlinecolor": outlinecolor,
            "textoutlinewidth": textoutlinewidth,
        }
        for gp in self.panels:
            # See if we have any data to plot, clip is trouble
            df = gdf.to_crs(gp.crs).cx[
                slice(*gp.get_xlim()), slice(*gp.get_ylim())
            ]
            for row in df.itertuples():
                self._place_value(gp, collider, row, **style)

    def _place_value(
        self,
        gp,
        collider,
        row,
        fmt,
        textsize,
        labeltextsize,
        labelcolor,
        showmarker,
        labelbuffer,
        outlinecolor,
        textoutlinewidth,
    ):
        """Draw one value (and label), unless it collides with prior text.

        The text is drawn first so its true rendered extent can be measured,
        then removed again if it collides with previously accepted text.
        """
        renderer = self.fig.canvas.get_renderer()
        x, y = row.geometry.x, row.geometry.y
        text = gp.text(
            x,
            y,
            fmt % (row.val,),
            color=row.color,
            size=textsize,
            zorder=row.zorder,
            va="bottom" if showmarker else "center",
            ha="center",
            crs=gp.crs,
        )
        text.set_clip_on(True)
        if row.backgroundcolor is not None:
            text.set_backgroundcolor(row.backgroundcolor)
        if textoutlinewidth > 0:
            text.set_path_effects(
                [
                    PathEffects.Stroke(
                        linewidth=textoutlinewidth, foreground=outlinecolor
                    ),
                    PathEffects.Normal(),
                ]
            )
        # Keep the text inside the axes by anchoring it to the point
        axbox = gp.ax.get_window_extent(renderer)
        extent = text.get_window_extent(renderer)
        if extent.x0 < axbox.x0:
            text.set_ha("left")
        elif extent.x1 > axbox.x1:
            text.set_ha("right")
        extent = text.get_window_extent(renderer)
        label = None
        if row.label:
            label = gp.ax.annotate(
                f"{row.label}",
                xy=(x, y),
                ha="center",
                va="top",
                xytext=(0, 0 - textsize / 2),
                color=labelcolor,
                textcoords="offset points",
                zorder=row.zorder - 1,
                clip_on=True,
                fontsize=labeltextsize,
            )
            extent = Bbox.union([extent, label.get_window_extent(renderer)])
        box = (extent.x0, extent.y0, extent.x1, extent.y1)
        if labelbuffer > 0:
            if not collider.try_claim(
                box, row.zorder, labelbuffer, labelbuffer * 0.75
            ):
                if self.debug:
                    LOG.warning("culling |%s| due to overlap", text.get_text())
                text.remove()
                if label is not None:
                    label.remove()
                return
        else:
            # Never culled, but still recorded for later labels to avoid
            collider.claim(box, row.zorder)
        if self.debug:
            # Red is the buffered collision box, black the rendered text
            xpad, ypad = labelbuffer, labelbuffer * 0.75
            for (bx0, by0, bx1, by1), edge in (
                (
                    (
                        box[0] - xpad,
                        box[1] - ypad,
                        box[2] + xpad,
                        box[3] + ypad,
                    ),
                    "r",
                ),
                (box, "k"),
            ):
                self.fig.patches.append(
                    Rectangle(
                        (bx0, by0),
                        bx1 - bx0,
                        by1 - by0,
                        facecolor="None",
                        edgecolor=edge,
                    )
                )
        if showmarker:
            gp.scatter(
                x, y, marker="+", zorder=row.zorder, color="k", crs=gp.crs
            )

    def scatter(self, lons, lats, vals, clevs, **kwargs):
        """Draw points on the map

        Args:
          lons (list): longitude values
          lats (list): latitude values
          vals (list): Data values for the points to use for colormapping
          clevs (list): Levels to use for ramp
          **kwargs: additional options
            draw_colorbar (bool, optional): Draw a colorbar, default True.
        """
        cmap = stretch_cmap(
            kwargs.get("cmap"), clevs, extend=kwargs.get("extend")
        )
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        colors = cmap(norm(vals))
        self.panels[0].scatter(
            lons,
            lats,
            c=colors,
            edgecolors=colors,
            crs=LATLON,
            zorder=Z_OVERLAY,
        )
        kwargs.pop("cmap", None)
        if kwargs.pop("draw_colorbar", True):
            self.draw_colorbar(clevs, cmap, norm, **kwargs)

    def hexbin(self, lons, lats, vals, clevs, **kwargs):
        """hexbin wrapper.

        Args:
            draw_colorbar (bool,optional): Draw colorbar default True.
        """
        cmap = kwargs.pop("cmap", None)
        cmap = stretch_cmap(cmap, clevs, extend=kwargs.get("extend"))
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        _hex = self.panels[0].hexbin(
            lons,
            lats,
            vals,
            norm=norm,
            cmap=cmap,
            zorder=Z_FILL,
        )
        if kwargs.pop("draw_colorbar", True):
            self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return _hex

    def imshow(
        self,
        grid: np.ndarray,
        affine: Affine,
        crs: str,
        clevs: Optional[list] = None,
        **kwargs,
    ):
        """Reprojects an image onto each MapPanel and then draws it.

        Args:
            grid (np.ndarray): The 2-D data to draw
            affine (Affine): The affine transformation of the image
            crs (str): The CRS of the image
            clevs (list, Optional): The levels to use for the colormap

        Keyword Args:
            draw_colorbar (bool,optional): Draw colorbar default True.
            cmap (str,optional): The colormap to use, default jet.
            extend (str,optional): The extend value for the colormap.
            clip_on (bool,optional): Clip the image to the map region.
        """
        if kwargs.get("norm") is None:
            cmap = stretch_cmap(
                kwargs.get("cmap", "jet"), clevs, extend=kwargs.get("extend")
            )
            norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        else:
            cmap = kwargs.get("cmap", "jet")
            norm = kwargs["norm"]
        # masked array is trouble with rasterio, at least for me
        if isinstance(grid, np.ma.MaskedArray):
            grid = grid.filled(np.nan)

        with rasterio.Env():
            for panel in self.panels:
                # Get the extent of the map region
                (west, east, south, north) = panel.get_extent()
                pbbox = panel.ax.get_window_extent()
                pdx = (east - west) / pbbox.width
                pdy = (north - south) / pbbox.height
                dest_aff = rasterio.Affine(pdx, 0, west, 0, pdy, south)
                reprojected = np.zeros((int(pbbox.height), int(pbbox.width)))
                # Reproject the image onto each panel
                reproject(
                    grid,
                    reprojected,
                    src_transform=affine,
                    src_crs=crs,
                    dst_transform=dest_aff,
                    dst_crs=panel.crs,
                    resampling=Resampling.nearest,
                    dst_nodata=np.nan,
                )
                # Draw the image
                panel.ax.imshow(
                    reprojected,
                    extent=(west, east, south, north),
                    origin="lower",
                    zorder=Z_FILL,
                    cmap=cmap,
                    norm=norm,
                    interpolation="nearest",
                ).set_rasterized(True)
        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop("cmap", None)
        kwargs.pop("norm", None)
        if kwargs.pop("draw_colorbar", True):
            self.draw_colorbar(clevs, cmap, norm, **kwargs)

    def pcolormesh(self, lons, lats, vals, clevs, **kwargs):
        """Opinionated mpl.pcolormesh wrapper.

        If you supply a lons in the same shape of the vals, this method will
        tack on an extra row and column to make matplotlib happy. If you do
        not want this, then pass your own lons + lats that is 1 column and 1
        row greater than vals.

        Args:
            lons (np.ndarray): The longitude values for the grid
            lats (np.ndarray): The latitude values for the grid
            vals (np.ndarray): The values to plot
            clevs (list): The levels to use for the colormap
            alpha (float,optional): The alpha value to use for the image,
              default 1.0.
            cmap (str,optional): The colormap to use, default jet.
            crs (str,optional): The CRS of the lons/lats, default LATLON.
            extend (str,optional): The extend value for the colormap.
            clip_on (bool,optional): Clip the image to the map region.
            draw_colorbar (bool,optional): Draw colorbar default True.

        Returns:
            res: The result of the pcolormesh call.
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

        res = self.panels[0].pcolormesh(
            lons,
            lats,
            vals,
            norm=norm,
            cmap=cmap,
            zorder=Z_FILL,
            crs=kwargs.pop("crs", LATLON),
            alpha=kwargs.pop("alpha", 1.0),
        )

        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop("cmap", None)
        if kwargs.pop("draw_colorbar", True):
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
            "fema_region",
        ):
            return
        # in lon,lat
        if sector == "state":
            s = load_geodf("us_states")
            mask_outside_geom(self.panels[0], s.at[self.state, "geom"])
            return
        if sector == "cwa":
            s = load_geodf("cwa")
            mask_outside_geom(self.panels[0], s.at[self.cwa, "geom"])
            return
        if sector == "fema_region":
            s = load_geodf("fema_regions")
            mask_outside_geom(self.panels[0], s.at[self.fema_region, "geom"])
            return
        if sector == "conus":
            s = load_geodf("conus")
            mask_outside_geom(self.panels[0], s.iloc[0]["geom"])
            return
        if sector == "iowawfo":
            s = load_geodf("iowawfo")
            geo = s["geom"].values[0]
            ccw = np.asarray(geo.exterior.coords)[::-1]
        else:
            ccw = load_bounds(f"{sector}_ccw")
        # in map coords
        x, y = self.panels[0].transform_lonlat(ccw[:, 0], ccw[:, 1])
        mask_outside_polygon(list(zip(x, y, strict=False)), self.panels[0])

    def contourf(self, lons, lats, vals, clevs, **kwargs):
        """Contourf

        Args:
          ilabel (boolean,optional): Should we label contours
          iline (boolean,optional): should we draw contour lines
          lblformat (str,optional): Format string for labeling contours, %.0f.
            draw_colorbar (bool,optional): Draw colorbar default True.
          linewidths (float,optional): Line width(s) for contour lines

        Returns:
          vals (np.array): The values used for plotting, maybe after gridding
        """
        if isinstance(lons, list):
            lons = np.array(lons)
            lats = np.array(lats)
            vals = np.array(vals)
        if np.array(vals).ndim == 1:
            # We need to grid, get current plot bounds in display proj
            # Careful here as a rotated crs may have maxes not in ul
            xbnds = self.panels[0].get_xlim()
            ybnds = self.panels[0].get_ylim()
            xi = np.linspace(xbnds[0], xbnds[1], 100)
            yi = np.linspace(ybnds[0], ybnds[1], 100)
            xi, yi = np.meshgrid(xi, yi)
            xproj, yproj = self.panels[0].transform_lonlat(lons, lats)
            nn = NearestNDInterpolator((xproj, yproj), vals)
            vals = nn(xi, yi)
            window = np.ones((6, 6))
            vals = convolve2d(
                vals, window / window.sum(), mode="same", boundary="symm"
            )
        else:
            xi, yi = self.panels[0].transform_lonlat(lons, lats)

        cmap = stretch_cmap(
            kwargs.get("cmap"), clevs, extend=kwargs.get("extend")
        )
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        self.panels[0].contourf(
            xi,
            yi,
            vals,
            clevs,
            cmap=cmap,
            norm=norm,
            zorder=Z_FILL,
            extend="both",
            crs=self.panels[0].crs,
        )
        if kwargs.get("iline", True):
            csl = self.panels[0].contour(
                xi,
                yi,
                vals,
                clevs,
                colors="w",
                zorder=Z_FILL_LABEL,
                crs=self.panels[0].crs,
                linewidths=kwargs.pop("linewidths", 1),
            )
            if kwargs.get("ilabel", False):
                # Legacy non-standardized kwarg
                lf = kwargs.get("lblformat", kwargs.get("labelfmt", "%.0f"))
                self.panels[0].ax.clabel(
                    csl,
                    fmt=lf,
                    colors="k",
                    fontsize=14,
                    zorder=Z_FILL_LABEL + 1,
                )
        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop("cmap", None)
        if kwargs.pop("draw_colorbar", True):
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
        """Overlay filled UGC geometries using bundled geometries.

        Note the importance of the `is_firewx` flag.  This determines which
        UGC database to look at in the face of ambiquity.

        Note that this will fail when provided a `data` dictionary that has
        both zones and counties.  It is recommended to plot from application
        logic with your own geometries in this instance.

        Args:
          data(dict): A dictionary of 6 char UGC code keys and values
          bins(list, optional): Bins to use for cloropleth, default 0:101:10
          color(dict, optional): Hard code what each UGC should display as
            for color.
          discontinued(bool, optional): Should we include discontinued UGCs
            within the baseline geodata for plotting, default is `False`.
          is_firewx(bool, optional): Are we plotting fire weather zones?
          draw_colorbar (bool, optional): Should a color bar be generated,
            default is `True`.
          plotmissing(bool, optional): Should missing UGC data be plotted?
          labels(dict, optional): UGC indexed dictionary to use for labeling.
          lblformat(str, optional): Format string for labels, default %s.
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
        geofn = "ugcs_county" if counties else f"ugcs_{zonesfn}"
        geodf = load_geodf(geofn, self.panels[0].crs.to_epsg())
        if kwargs.get("discontinued", False):
            geodf2 = load_geodf(
                f"{geofn}_discontinued", self.panels[0].crs.to_epsg()
            ).to_crs(geodf.crs)
            geodf = pd.concat([geodf, geodf2])
        if self.sector == "state":
            geodf = geodf[geodf.index.str.slice(0, 2) == self.state]
        elif self.sector == "cwa":
            geodf = geodf[geodf["cwa"] == self.cwa]
        polygon_fill(self, geodf, data, **kwargs)

    def fill_states(self, data, **kwargs):
        """Add overlay of filled state polygons"""
        geodf = load_geodf("us_states")
        if self.sector in ["nws", "conus"]:
            st = ["NH", "MD", "CT"]
            geodf.loc[st, "lat"] = geodf.loc[st, "lat"] - 0.3
            st = ["VT", "DE"]
            geodf.loc[st, "lat"] = geodf.loc[st, "lat"] + 0.3
        polygon_fill(self, geodf, data, **kwargs)
        if self.sector != "nws":
            return
        # States that may have data, but are not plotted within sector=nws
        msg = ["Not Plotted:"]
        for st in "VI MH MP DC".split():  # eh, are there more?
            if st in data:
                val = kwargs.get("lblformat", "%s") % (data[st],)
                msg.append(f"{st}: {val}")
        if len(msg) > 1:
            self.ax.text(
                0.99,
                0.4,
                "\n".join(msg),
                ha="right",
                va="top",
                fontsize=10,
                bbox=dict(color="white"),
                transform=self.ax.transAxes,
            )

    def draw_fema_regions(self, color: str = "k", **kwargs):
        """Overlay FEMA Regions."""
        kwargs["edgecolor"] = color
        regions = load_geodf("fema_regions")
        for gp in self.panels:
            regions.to_crs(gp.crs).plot(
                ax=gp.ax,
                aspect=None,
                zorder=Z_POLITICAL,
                facecolor="None",
                add_labels=False,
                **kwargs,
            )

    def fill_fema_regions(self, data, **kwargs):
        """Add overlay of filled polygons for FEMA Regions.

        Data is dictionary-ish and keys should be ints!
        """
        geodf = load_geodf("fema_regions")
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
        for gp in self.panels:
            cwas.to_crs(gp.crs).plot(
                ax=gp.ax,
                aspect=None,
                zorder=Z_POLITICAL,
                facecolor="None",
                add_labels=False,
                **kwargs,
            )

    def fill_rfc(self, data, **kwargs):
        """Add overlay of filled polygons for NWS RFCs.

        Data is dictionary-ish.  Note that the ids used here are the WMO
        center IDs (ie TAR) and not basin ids (ie NERFC)
        """
        geodf = load_geodf("rfc")
        polygon_fill(self, geodf, data, **kwargs)

    def fill_cwsu(self, data, **kwargs):
        """Add overlay of filled polygons for NWS CWSUs.

        Data is dictionary-ish.
        """
        geodf = load_geodf("cwsu")
        # Fix troublesome points
        geodf.loc["ZAN", "lat"] = 64.5
        polygon_fill(self, geodf, data, **kwargs)

    def fill_cwas(self, data, **kwargs):
        """Add overlay of filled polygons for NWS Forecast Offices.

        Method adds a colorized overlay of NWS Forecast Offices based on a
        data dictionary of values provided. This method also places a color
        bar on the image.

        Args:
          data (dict): Dictionary of values with keys representing the 3 char
            or 4 char idenitifer for the WFO.  This assumes the 3 char sites
            are the K ones.
          ilabel (bool): Should we label?
        """
        geodf = load_geodf("cwa")
        # Painfull.  San Juan's WFO identifier is SJU, but VTEC uses JSJ, our
        # plotting here uses SJU
        if "JSJ" in data:
            data["SJU"] = data["JSJ"]
        # Goose some points to improve readability
        if self.sector in ["nws", "conus"]:
            geodf.loc["MLB", "lat"] = geodf.loc["MLB", "lat"] + 0.2
            geodf.loc["TBW", "lat"] = geodf.loc["TBW", "lat"] - 0.1
            geodf.loc["BUF", "lat"] = geodf.loc["BUF", "lat"] + 0.2
            geodf.loc["BGM", "lat"] = geodf.loc["BGM", "lat"] - 0.1
            geodf.loc["DTX", "lat"] = geodf.loc["DTX", "lat"] + 0.3
            geodf.loc["GRR", "lat"] = geodf.loc["GRR", "lat"] - 0.3

            geodf.loc["MHX", "lon"] = geodf.loc["MHX", "lon"] + 0.2
            geodf.loc["RAH", "lon"] = geodf.loc["RAH", "lon"] - 0.2
        polygon_fill(self, geodf, data, **kwargs)

    def drawcities(self, **kwargs):
        """Overlay some cities

        Args:
          minpop (int,optional): Minimum population to consider for plotting.
          labelbuffer (int): approximate number of pixels to compute overlap
          textsize (int): size of the text
          color (str): color to plot the text with
          outlinecolor (str): color to outline the text with
          isolated (bool): Cause `plot_values` to do label collision against
            only labels from drawing cities. Default False.
        """
        gdf = load_geodf("cities")
        (west, east, south, north) = self.panels[0].get_extent(crs=LATLON)
        minpop = kwargs.pop(
            "minpop", 50000.0 if self.sector in ["nws", "conus"] else 5000.0
        )
        df2 = gdf.cx[west:east, south:north].query(f"pop_2010 > {minpop}")
        # hack around a API break
        tsz = kwargs.pop("textsize", 16)
        self.plot_values(
            df2["geom"].x,
            df2["geom"].y,
            df2["name"].values,
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
        for gp in self.panels:
            df = geodf.to_crs(gp.crs).cx[
                slice(*gp.get_xlim()), slice(*gp.get_ylim())
            ]
            if not df.empty:
                df.plot(
                    ax=gp.ax,
                    aspect=None,
                    facecolor="None",
                    edgecolor=color,
                    lw=0.4,
                    zorder=Z_OVERLAY2 + 2,
                    add_labels=False,
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
        with BytesIO() as ram:
            self.fig.savefig(ram, format="png")
            imgdata = ram.getvalue()
        if kwargs.get("memcache") and kwargs.get("memcachekey"):
            kwargs["memcache"].set(
                kwargs["memcachekey"],
                imgdata,
                time=kwargs.get("memcacheexpire", 300),
            )
        if kwargs.get("web", False):
            ssw("Content-Type: image/png\n\n")
            sys.stdout.buffer.write(imgdata)
            return
        with tempfile.NamedTemporaryFile(delete=False) as tmpfd:
            tmpfd.write(imgdata)
        if kwargs.get("pqstr") is not None:
            subprocess.call(["pqinsert", "-p", kwargs["pqstr"], tmpfd.name])
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
            valid = valid.astimezone(timezone.utc)
        url = (
            "https://mesonet.agron.iastate.edu/"
            "api/1/iowa_winter_roadcond.geojson"
        )
        tstamp = valid.strftime("%Y-%m-%d %H:%M")
        try:
            resp = requests.get(url, params={"valid": tstamp}, timeout=30)
            resp.raise_for_status()
            df = gpd.GeoDataFrame().from_features(resp.json())
        except Exception as exp:
            warnings.warn(f"overlay_roadcond failed: {exp}", stacklevel=1)
            return
        labels = []
        for _, row in df.iterrows():
            for geo in row["geometry"].geoms:
                self.panels[0].plot(
                    *geo.xy,
                    crs=LATLON,
                    color=row["color"],
                    linewidth=2 if row["rtype"] > 1 else 4,
                    zorder=Z_OVERLAY2,
                    label=None if row["label"] in labels else row["label"],
                )
                if row["label"] not in labels:
                    labels.append(row["label"])
        self.panels[0].ax.legend(
            loc=3,
            ncol=6,
            fontsize=10,
            facecolor="white",
            framealpha=1,
        ).set_zorder(Z_OVERLAY2 + 5)

    def overlay_nexrad(self, valid=None, product="N0Q", caxpos=None):
        """Overlay an IEM NEXRAD Composite Image.

        Args:
          valid (datetime.datetime): Valid time for NEXRAD overlay.
          product (str): either N0Q or N0R for the mosaic type.
          caxpos (array-like): `matplotlib.axes.set_position` value for the
            colorbar.  Defaults to something in the upper-right.

        Returns:
          valid time of the NEXRAD, or None if not found.
        """
        if valid is None:
            valid = utc()
        if hasattr(valid, "tzinfo"):
            valid = valid.astimezone(timezone.utc)
        if product not in ["N0R", "N0Q"]:
            raise ValueError("nexrad `product` not in {N0R,N0Q}")
        # Rectify to modulus 5 minutes
        valid -= timedelta(minutes=valid.minute % 5)
        compsector = "us"
        if self.sector == "state" and self.state in ["AK", "HI", "PR", "GU"]:
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
        elif self.sector == "cwa" and self.cwa in [
            "GUM",
        ]:
            compsector = "gu"
        baseurl = valid.strftime(
            "https://mesonet.agron.iastate.edu/archive/data/%Y/%m/%d/"
            f"GIS/{compsector}comp/{product.lower()}_%Y%m%d%H%M."
        )
        try:
            resp_png = requests.get(f"{baseurl}png", timeout=10)
            resp_png.raise_for_status()
            resp_wld = requests.get(f"{baseurl}wld", timeout=10)
            resp_wld.raise_for_status()
        except requests.exceptions.RequestException as exp:
            LOG.warning(exp)
            return None
        # World file defines the center of the upper left pixel
        (dx, _, _, dy, west, north) = [
            float(x) for x in resp_wld.content.decode("ascii").split("\n")
        ]
        west_edge = west - dx / 2.0
        north_edge = north + dy / 2.0
        bio = BytesIO(resp_png.content)
        bio.seek(0)
        with Image.open(bio) as pilimg:
            # Horrid hack, the IEM archive added a placeholder file that was
            # RGB instead of mode=P
            _zeros = np.zeros((100, 100))
            im = np.asarray(pilimg) if pilimg.size != (100, 100) else _zeros

        ramp = ramp2df(f"composite_{product.lower()}")
        cmap = mpcolors.ListedColormap(
            ramp[["r", "g", "b"]].to_numpy() / 256
        ).with_extremes(under=(0, 0, 0, 0))
        norm = mpcolors.BoundaryNorm(ramp["coloridx"].values, cmap.N)
        self.imshow(
            im,
            Affine(dx, 0, west_edge, 0, dy, north_edge),
            "EPSG:4326",
            cmap=cmap,
            norm=norm,
            draw_colorbar=False,
            clip_on=False,
        )

        pos = self.panels[0].ax.get_position()
        cax = self.fig.add_axes(
            caxpos or (pos.x1 - 0.35, pos.y1 - 0.01, 0.35, 0.015)
        )
        # pylint: disable=unsubscriptable-object
        cb = self.fig.colorbar(
            mpcm.ScalarMappable(norm=norm, cmap=cmap),
            cax=cax,
            ticks=ramp.loc[ramp["value"] % 20 == 0]["coloridx"].values,
            extend="neither",
            orientation="horizontal",
            drawedges=False,
            ticklocation="top",
        )
        # Needed with matplotlib 3.6.0
        cax.minorticks_on()
        # pylint: disable=no-member,consider-using-f-string
        cb.set_ticklabels(
            [
                "%.0d" % (d,)
                for d in ramp.loc[ramp["value"] % 20 == 0]["value"].values
            ]
        )
        if caxpos is not None:
            pos = cb.ax.get_position()
        self.fig.text(pos.x1, pos.y1 + 0.005, "dBZ", ha="left")
        return valid
