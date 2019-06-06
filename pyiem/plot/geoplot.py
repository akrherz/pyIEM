# -*- coding: utf-8 -*-
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
from __future__ import print_function
from io import BytesIO
import tempfile
import os
import sys
import subprocess
import shutil
import pickle
import datetime
import math
import warnings
import logging
#
import requests
import numpy as np
import pandas as pd
import geojson
from shapely.geometry import shape
#
from scipy.signal import convolve2d
from scipy.interpolate import NearestNDInterpolator
#
from PIL import Image
# Matplotlib
from matplotlib.patches import Polygon
import matplotlib.colors as mpcolors
import matplotlib.image as mpimage
from matplotlib.patches import Wedge
import matplotlib.colorbar as mpcolorbar
import matplotlib.patheffects as PathEffects
# cartopy
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from pyiem.plot.use_agg import plt
from pyiem.plot.util import (
    sector_setter, mask_outside_polygon, polygon_fill, mask_outside_geom)
from pyiem.reference import (  # noqa: F401  # pylint: disable=unused-import
    Z_CF, Z_FILL, Z_FILL_LABEL, Z_CLIP, Z_CLIP2, Z_POLITICAL, Z_OVERLAY,
    Z_OVERLAY2)
from pyiem.util import ssw
from pyiem.datatypes import speed, direction
from pyiem.plot.colormaps import stretch_cmap
import pyiem.meteorology as meteorology

# we ran the cartopy/tools downloader
cartopy.config['pre_existing_data_dir'] = '/opt/miniconda3/cartopy_data/'
# Set a saner default for apache et al
cartopy.config['data_dir'] = '/tmp/'
logging.basicConfig()


DATADIR = os.sep.join([os.path.dirname(__file__), '..', 'data'])
MAIN_AX_BOUNDS = [0.01, 0.05, 0.898, 0.85]
CAX_BOUNDS = [0.917, 0.1, 0.02, 0.8]


def centered_bins(absmax, _on=0, bins=9):
    """Return a smooth binning

    Args:
      absmax (real): positive absolute value we want or bins to enclose
      on (real): where to center the bins at (TODO)
      bins (int): number of bins to generate
    Returns:
      list of bins"""
    mx = (bins-1)/2.
    width = absmax / float(mx)
    if width > 1:
        width = math.ceil(width)
    else:
        return np.linspace(0 - absmax, absmax, bins)
    return np.arange(0 - mx, mx + 1) * width


def true_filter(_bm, _key, _val):
    """Always return true"""
    return True


def cwa_filter(bm, _key, val):
    """A filter for checking a key against current plot"""
    return val.get(b'cwa', b'').decode('utf-8') == bm.cwa


def state_filter(bm, key, _val):
    """A filter for checking a key against current plot"""
    return key[:2].decode('utf-8') == bm.state


def load_bounds(filebase):
    """Load bounds file

    Args:
      filebase (str): the basename of the file containing the data

    Returns:
      numpy 2d array of the data
    """
    fn = "%s/%s.npy" % (DATADIR, filebase)
    if not os.path.isfile(fn):
        print("load_bounds(%s) is missing!" % (fn,))
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
        print("load_pickle_pd(%s) failed, file is missing" % (fn,))
        return fn
    return pd.read_pickle(fn)


def load_pickle_geo(filename):
    """Load pickled dictionaries containing geometries and other metadata

    Args:
      filename(str): The filename to load, contained in project data/

    Returns:
      dict: The dictionary of data
    """
    fn = "%s/%s" % (DATADIR, filename)
    if not os.path.isfile(fn):
        print("load_pickle_geo(%s) failed, file is missing!" % (fn,))
        return dict()
    pickle_opts = dict()
    if sys.version_info.major > 2:
        pickle_opts['encoding'] = 'bytes'
    return pickle.load(open(fn, 'rb'), **pickle_opts)


class MapPlot(object):
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

    def __init__(self, sector='iowa', figsize=(10.24, 7.68), **kwargs):
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
        """
        self.debug = kwargs.get('debug', False)
        self.fig = plt.figure(num=None, figsize=figsize,
                              dpi=kwargs.get('dpi', 100))
        # Storage of axes within this plot
        self.state = None
        self.cwa = None
        self.textmask = None  # For our plot_values magic, to prevent overlap
        self.sector = sector
        self.cax = plt.axes(CAX_BOUNDS, frameon=False,
                            yticks=[], xticks=[])
        self.axes = []
        self.ax = None
        # hack around sector=iowa
        if self.sector == 'iowa':
            self.sector = 'state'
            self.state = 'IA'
        sector_setter(self, MAIN_AX_BOUNDS, **kwargs)

        for _a in self.axes:
            if _a is None:
                continue
            # legacy usage of axisbg here
            _c = kwargs.get('axisbg',
                            kwargs.get('continentalcolor',
                                       '#EEEEEE'))
            _a.add_feature(cfeature.LAND, facecolor=_c, zorder=Z_CF)
            coasts = cfeature.NaturalEarthFeature('physical', 'coastline',
                                                  '10m',
                                                  edgecolor='black',
                                                  facecolor='none')
            _a.add_feature(coasts, lw=1.0, zorder=Z_POLITICAL)
            _a.add_feature(cfeature.BORDERS, lw=1.0, zorder=Z_POLITICAL)
            _a.add_feature(cfeature.OCEAN, facecolor=(0.4471, 0.6235, 0.8117),
                           zorder=Z_CF)
            _a.add_feature(cfeature.LAKES, facecolor=(0.4471, 0.6235, 0.8117),
                           zorder=Z_CF)
            if 'nostates' not in kwargs:
                states = load_pickle_geo('us_states.pickle')
                _a.add_geometries(
                    [val[b'geom'] for key, val in states.items()],
                    crs=ccrs.PlateCarree(), lw=1.0,
                    edgecolor=kwargs.get('statebordercolor', 'k'),
                    facecolor='None', zorder=Z_POLITICAL
                )

        if not kwargs.get('nologo'):
            self.iemlogo()
        if "title" in kwargs:
            self.fig.text(0.09 if not kwargs.get('nologo') else 0.02, 0.94,
                          kwargs.get("title"),
                          fontsize=kwargs.get('titlefontsize', 18))
        if "subtitle" in kwargs:
            self.fig.text(0.09 if not kwargs.get('nologo') else 0.02, 0.91,
                          kwargs.get("subtitle"),
                          fontsize=kwargs.get('subtitlefontsize', 12))

        if 'nocaption' not in kwargs:
            self.fig.text(0.01, 0.03, ("%s :: generated %s"
                                       ) % (
                    kwargs.get('caption', 'Iowa Environmental Mesonet'),
                    datetime.datetime.now().strftime("%d %B %Y %I:%M %p %Z"),))

    def close(self):
        ''' Close the figure in the case of batch processing '''
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
        hatches = ['+', '/', "\\", '-', 'x']
        if valid is None:
            valid = ''
        elif isinstance(valid, datetime.date):
            valid = valid.strftime("%Y-%m-%d")
        elif isinstance(valid, datetime.datetime):
            valid = valid.strftime("%Y-%m-%d")
        url = ("http://mesonet.agron.iastate.edu/geojson/usdm.py?date=%s"
               ) % (valid,)
        try:
            req = requests.get(url, timeout=30)
        except requests.ConnectionError as exp:
            warnings.warn("draw_usdm IEM USDM Webservice failed: %s" % (exp,))
            return None
        feats = geojson.loads(req.content)
        lw = 1 if filled else 4.
        usdm_valid = None
        for record in feats.features:
            color = colors[record.properties['dm']]
            geom = shape(record['geometry'])
            usdm_valid = record.properties['date']
            fc = color if filled else 'None'
            ec = color if not filled else 'k'
            self.ax.add_geometries([geom], ccrs.PlateCarree(),
                                   facecolor='None',
                                   edgecolor=ec, linewidth=lw,
                                   zorder=Z_OVERLAY2)
            if filled:
                self.ax.add_geometries([geom], ccrs.PlateCarree(),
                                       facecolor=fc, alpha=0.5,
                                       edgecolor='None', zorder=Z_OVERLAY)
            elif hatched:
                self.ax.add_geometries([geom], ccrs.PlateCarree(),
                                       facecolor='None',
                                       hatch=hatches[record.properties['dm']],
                                       edgecolor=color, zorder=Z_OVERLAY2 + 2)

        if usdm_valid is not None:
            self.ax.text(0.99, 0.99, "D4", color='k',
                         transform=self.ax.transAxes, va='top', ha='right',
                         bbox=dict(color=colors[4]), zorder=Z_OVERLAY2 + 3)
            self.ax.text(0.955, 0.99, "D3", color='k',
                         transform=self.ax.transAxes, va='top', ha='right',
                         bbox=dict(color=colors[3]), zorder=Z_OVERLAY2 + 3)
            self.ax.text(0.92, 0.99, "D2", color='k',
                         transform=self.ax.transAxes, va='top', ha='right',
                         bbox=dict(color=colors[2]), zorder=Z_OVERLAY2 + 3)
            self.ax.text(0.885, 0.99, "D1", color='k',
                         transform=self.ax.transAxes, va='top', ha='right',
                         bbox=dict(color=colors[1]), zorder=Z_OVERLAY2 + 3)
            self.ax.text(0.85, 0.99, "D0", color='k',
                         transform=self.ax.transAxes, va='top', ha='right',
                         bbox=dict(color=colors[0]), zorder=Z_OVERLAY2 + 3)
            self.ax.text(0.815, 0.99, 'USDM %s' % (usdm_valid,), color='w',
                         transform=self.ax.transAxes, va='top', ha='right',
                         bbox=dict(color='k'), zorder=Z_OVERLAY2 + 3)
            return datetime.datetime.strptime(usdm_valid, '%Y-%m-%d')
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

        clevlabels = kwargs.get('clevlabels', clevs)

        under = clevs[0] - (clevs[1] - clevs[0])
        over = clevs[-1] + (clevs[-1] - clevs[-2])
        extend = kwargs.get('extend', 'both')
        # inspect the cmap to see if we need to do any extensions
        # pylint: disable=protected-access
        if cmap._rgba_under is not None and cmap._rgba_over is None:
            blevels = np.concatenate([[under, ], clevs])
        elif cmap._rgba_under is None and cmap._rgba_over is not None:
            blevels = np.concatenate([clevs, [over, ]])
        elif cmap._rgba_under is not None and cmap._rgba_over is not None:
            blevels = np.concatenate([[under, ], clevs, [over, ]])
        else:
            blevels = clevs
        stride = slice(None, None, int(kwargs.get('clevstride', 1)))
        cb2 = mpcolorbar.ColorbarBase(
            self.cax, cmap=cmap, norm=norm, boundaries=blevels,
            extend=extend, ticks=clevs[stride],
            spacing=kwargs.get('spacing', 'uniform'), orientation='vertical'
        )

        def _myrepr(val):
            """avoid list conversion in matplotlib that fowls numpy floats."""
            try:
                return "%g" % (val, )
            except TypeError:
                return "%s" % (val, )
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

        if 'units' in kwargs:
            self.fig.text(
                0.99, 0.03, "data units :: %s" % (kwargs['units'],),
                ha='right'
            )

        title = kwargs.get('title')
        if title:
            self.ax.set_position(
                [MAIN_AX_BOUNDS[0],
                 MAIN_AX_BOUNDS[1],
                 MAIN_AX_BOUNDS[2] - 0.03,
                 MAIN_AX_BOUNDS[3]]
            )
            cb2.ax.text(
                -0.05, 0.5, title, rotation=90, fontsize=16,
                transform=cb2.ax.transAxes, ha='right', va='center'
            )

    def plot_station(self, data, **kwargs):
        """Plot values on a map in a station plot like manner.

        Args:
          data (list): list of dicts with station data to plot
          fontsize (int): font size to use for plotted text
        """
        (x0, x1) = self.ax.set_xlim()
        # size to use for circles
        circlesz = (x1 - x0) / 180.
        # (y0, y1) = self.ax.set_ylim()
        offsets = {1: [-4, 4, 'right', 'bottom'],
                   2: [0, 4, 'center', 'bottom'],
                   3: [4, 4, 'left', 'bottom'],
                   4: [-4, 0, 'right', 'center'],
                   5: [0, 0, 'center', 'center'],
                   6: [4, 0, 'left', 'center'],
                   7: [-4, -4, 'right', 'top'],
                   8: [0, -4, 'center', 'top'],
                   9: [4, -4, 'left', 'top']}

        mask = np.zeros(self.fig.canvas.get_width_height(), bool)
        for stdata in data:
            (x, y) = self.ax.projection.transform_point(stdata['lon'],
                                                        stdata['lat'],
                                                        ccrs.Geodetic())
            (imgx, imgy) = self.ax.transData.transform([x, y])
            imgx = int(imgx)
            imgy = int(imgy)
            # Check to see if this overlaps
            _cnt = np.sum(np.where(mask[imgx-15:imgx+15, imgy-15:imgy+15], 1,
                                   0))
            if _cnt > 5:
                continue
            mask[imgx-15:imgx+15, imgy-15:imgy+15] = True
            # Plot bars
            if stdata.get('sknt') is not None and stdata['sknt'] > 1:
                (u, v) = meteorology.uv(speed(stdata.get('sknt', 0), 'KT'),
                                        direction(stdata.get('drct', 0),
                                                  'DEG'))
                if u is not None and v is not None:
                    self.ax.barbs(x, y, u.value('KT'), v.value('KT'), zorder=1)

            # Sky Coverage
            skycoverage = stdata.get('coverage')
            if (skycoverage is not None and skycoverage >= 0 and
                    skycoverage <= 100):
                w = Wedge((x, y), circlesz, 0, 360, ec='k', fc='white',
                          zorder=2)
                self.ax.add_artist(w)
                w = Wedge((x, y), circlesz, 0, 360. * skycoverage / 100.,
                          ec='k', fc='k', zorder=3)
                self.ax.add_artist(w)

            # Temperature
            val = stdata.get('tmpf')
            if val is not None:
                (offx, offy, ha, va) = offsets[1]
                self.ax.annotate(
                    stdata.get("tmpf_format", "%.0f") % (val, ),
                    xy=(x, y), ha=ha, va=va,
                    xytext=(offx, offy), color=stdata.get('tmpf_color', 'r'),
                    textcoords="offset points",
                    zorder=Z_OVERLAY+2,
                    clip_on=True, fontsize=kwargs.get('fontsize', 8))
            # Dew Point
            val = stdata.get('dwpf')
            if val is not None:
                (offx, offy, ha, va) = offsets[7]
                self.ax.annotate(
                    stdata.get("dwpf_format", "%.0f") % (val, ),
                    xy=(x, y), ha=ha, va=va,
                    xytext=(offx, offy), color=stdata.get('dwpf_color', 'b'),
                    textcoords="offset points",
                    zorder=Z_OVERLAY+2,
                    clip_on=True, fontsize=kwargs.get('fontsize', 8))
            # Plot identifier
            val = stdata.get('id')
            if val is not None:
                (offx, offy, ha, va) = (
                    offsets[6] if skycoverage is not None else offsets[5]
                )
                self.ax.annotate(
                    "%s" % (val, ), xy=(x, y), ha=ha, va=va,
                    xytext=(offx, offy),
                    color=stdata.get('id_color', 'tan'),
                    textcoords="offset points",
                    zorder=Z_OVERLAY+2,
                    clip_on=True,
                    fontsize=kwargs.get('fontsize', 8))

    def plot_values(self, lons, lats, vals, fmt='%s', valmask=None,
                    color='#000000', textsize=14, labels=None,
                    labeltextsize=10, labelcolor='#000000',
                    showmarker=False, labelbuffer=25, outlinecolor='#FFFFFF'):
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
          labelbuffer (int): pixel buffer around labels
          outlinecolor (color): color to use for text outlines
        """
        if valmask is None:
            valmask = [True] * len(lons)
        if labels is None:
            labels = [''] * len(lons)
        if isinstance(color, str):
            color = [color] * len(lons)
        bbox = self.fig.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted())
        axbbox = self.ax.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted())
        axx0 = axbbox.x0 * self.fig.dpi
        axx1 = (axbbox.x0 + axbbox.width) * self.fig.dpi
        axy0 = axbbox.y0 * self.fig.dpi
        axy1 = (axbbox.y0 + axbbox.height) * self.fig.dpi
        figwidth = bbox.width * self.fig.dpi
        figheight = bbox.height * self.fig.dpi
        if self.textmask is None:
            self.textmask = np.zeros((int(figwidth), int(figheight)), bool)
        thisax = self.ax
        # Create a fake label, to test out our scaling
        t0 = self.fig.text(0.5, 0.5, "ABCDEFGHIJ", transform=thisax.transAxes,
                           color='None', size=textsize)
        bbox = t0.get_window_extent(self.fig.canvas.get_renderer())
        xpixels_per_char = bbox.width / 10.
        ypixels = bbox.height
        for o, a, v, m, c, label in zip(lons, lats, vals, valmask,
                                        color, labels):
            if not m:
                continue

            ha = 'center'
            mystr = fmt % (v,)
            max_mystr_len = max([len(s) for s in mystr.split("\n")])
            mystr_lines = len(mystr.split("\n"))
            # compute the pixel coordinate of this data point
            (x, y) = thisax.projection.transform_point(o, a, ccrs.Geodetic())
            (imgx, imgy) = thisax.transData.transform([x, y])
            imgx0 = int(imgx - (max_mystr_len * xpixels_per_char / 2.0))
            if imgx0 < axx0:
                ha = 'left'
                imgx0 = imgx
            imgx1 = imgx0 + max_mystr_len * xpixels_per_char
            if imgx1 > axx1:
                imgx1 = imgx
                imgx0 = imgx1 - max_mystr_len * xpixels_per_char
                ha = 'right'
            imgy0 = int(imgy)
            imgy1 = imgy0 + mystr_lines * ypixels
            # Now we buffer
            imgx0 = max([0, imgx0 - labelbuffer])
            imgx1 = min([figwidth, (imgx0 + 2 * labelbuffer +
                                    max_mystr_len * xpixels_per_char)])
            imgy0 = max([0, imgy0 - labelbuffer * 0.75])
            imgy1 = min([figheight, (imgy0 +
                                     mystr_lines * ypixels +
                                     2 * labelbuffer * 0.75)])
            _cnt = np.sum(np.where(self.textmask[int(imgx0):int(imgx1),
                                                 int(imgy0):int(imgy1)],
                                   1, 0))
            # If we have more than 15 pixels of overlap, don't plot this!
            if _cnt > 15:
                if self.debug:
                    print("culling |%s| due to overlap, %s" % (repr(mystr),
                                                               _cnt))
                continue
            if self.debug:
                rec = plt.Rectangle([imgx0,
                                     imgy0],
                                    (imgx1 - imgx0),
                                    (imgy1 - imgy0),
                                    facecolor='None', edgecolor='r')
                self.fig.patches.append(rec)
            # Useful for debugging this algo
            if self.debug:
                print(("label: %s imgx: %s/%s-%s imgy: %s/%s-%s "
                       "x:%s-%s y:%s-%s _cnt:%s"
                       ) % (repr(mystr), imgx, axx0, axx1, imgy, axy0, axy1,
                            imgx0, imgx1, imgy0, imgy1, _cnt))
            self.textmask[int(imgx0):int(imgx1), int(imgy0):int(imgy1)] = True
            t0 = thisax.text(o, a, mystr, color=c,
                             size=textsize, zorder=Z_OVERLAY+2,
                             va='center' if not showmarker else 'bottom',
                             ha=ha, transform=ccrs.PlateCarree())
            bbox = t0.get_window_extent(self.fig.canvas.get_renderer())
            if self.debug:
                rec = plt.Rectangle([bbox.x0, bbox.y0],
                                    bbox.width, bbox.height,
                                    facecolor='None', edgecolor='k')
                self.fig.patches.append(rec)
            if showmarker:
                thisax.scatter(o, a, marker='+', zorder=Z_OVERLAY+2,
                               color='k', transform=ccrs.PlateCarree())
            t0.set_clip_on(True)
            t0.set_path_effects([PathEffects.Stroke(linewidth=3,
                                                    foreground=outlinecolor),
                                 PathEffects.Normal()])

            if label and label != '':
                thisax.annotate("%s" % (label, ), xy=(x, y), ha='center',
                                va='top',
                                xytext=(0, 0 - textsize/2),
                                color=labelcolor,
                                textcoords="offset points",
                                zorder=Z_OVERLAY+1,
                                clip_on=True, fontsize=labeltextsize)

    def scatter(self, lons, lats, vals, clevs, **kwargs):
        """Draw points on the map

        Args:
          lons (list): longitude values
          lats (list): latitude values
          vals (list): Data values for the points to use for colormapping
          clevs (list): Levels to use for ramp
          **kwargs: additional options
        """
        cmap = stretch_cmap(kwargs.get('cmap'), clevs)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        colors = cmap(norm(vals))
        self.ax.scatter(lons, lats, c=colors, edgecolors=colors,
                        transform=ccrs.PlateCarree(), zorder=Z_OVERLAY)
        kwargs.pop('cmap', None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)

    def hexbin(self, lons, lats, vals, clevs, **kwargs):
        """ hexbin wrapper """
        cmap = stretch_cmap(kwargs.get('cmap'), clevs)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        points = self.ax.projection.transform_points(ccrs.PlateCarree(),
                                                     lons, lats)
        _hex = self.ax.hexbin(points[:, 0], points[:, 1], C=vals, norm=norm,
                              cmap=cmap, zorder=Z_FILL)
        kwargs.pop('cmap', None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return _hex

    def pcolormesh(self, lons, lats, vals, clevs, **kwargs):
        """ pcolormesh wrapper """
        cmap = stretch_cmap(kwargs.get('cmap'), clevs)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        res = self.ax.pcolormesh(lons, lats, vals, norm=norm,
                                 cmap=cmap, zorder=Z_FILL,
                                 transform=ccrs.PlateCarree())

        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop('cmap', None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return res

    def draw_mask(self):
        """Draw the mask, when appropriate"""
        # can't mask what we don't know
        if self.sector not in (
                'iailin', 'midwest', 'conus', 'state', 'iowawfo', 'cwa'):
            return
        # in lon,lat
        if self.sector == 'state':
            s = load_pickle_geo('us_states.pickle')
            mask_outside_geom(self.ax, s[self.state.encode()][b'geom'])
            return
        elif self.sector == 'cwa':
            s = load_pickle_geo('cwa.pickle')
            mask_outside_geom(self.ax, s[self.cwa.encode()][b'geom'])
            return
        elif self.sector == 'iowawfo':
            s = load_pickle_geo('iowawfo.pickle')
            geo = s[b'iowawfo'][b'geom']
            ccw = np.asarray(geo.exterior)[::-1]
        else:
            ccw = load_bounds('%s_ccw' % (self.sector,))
        # in map coords
        points = self.ax.projection.transform_points(ccrs.Geodetic(),
                                                     ccw[:, 0], ccw[:, 1])
        mask_outside_polygon(points[:, :2], ax=self.ax)

    def contourf(self, lons, lats, vals, clevs, **kwargs):
        """ Contourf

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
            ll = ccrs.Geodetic().transform_point(xbnds[0], ybnds[0],
                                                 self.ax.projection)
            ul = ccrs.Geodetic().transform_point(xbnds[0], ybnds[1],
                                                 self.ax.projection)
            ur = ccrs.Geodetic().transform_point(xbnds[1], ybnds[1],
                                                 self.ax.projection)
            lr = ccrs.Geodetic().transform_point(xbnds[1], ybnds[0],
                                                 self.ax.projection)
            xi = np.linspace(min(ll[0], ul[0]), max(lr[0], ur[0]), 100)
            yi = np.linspace(min(ll[1], ul[1]), max(ul[1], ur[1]), 100)
            xi, yi = np.meshgrid(xi, yi)
            nn = NearestNDInterpolator((lons, lats), vals)
            vals = nn(xi, yi)
            lons = xi
            lats = yi
            window = np.ones((6, 6))
            vals = convolve2d(vals, window / window.sum(), mode='same',
                              boundary='symm')
        if lons.ndim == 1:
            lons, lats = np.meshgrid(lons, lats)

        cmap = stretch_cmap(kwargs.get('cmap'), clevs)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        # vals = maskoceans(lons, lats, vals, resolution='h')
        self.ax.contourf(lons, lats, vals, clevs,
                         cmap=cmap, norm=norm, zorder=Z_FILL,
                         extend='both', transform=ccrs.PlateCarree())
        if kwargs.get('iline', True):
            csl = self.ax.contour(lons, lats, vals, clevs, colors='w',
                                  zorder=Z_FILL_LABEL,
                                  transform=ccrs.PlateCarree())
            if kwargs.get('ilabel', False):
                self.ax.clabel(csl, fmt=kwargs.get('labelfmt', '%.0f'),
                               colors='k', fontsize=14)
        if kwargs.get("clip_on", True):
            self.draw_mask()
        kwargs.pop('cmap', None)
        self.draw_colorbar(clevs, cmap, norm, **kwargs)
        return vals

    def fill_climdiv(self, data, **kwargs):
        """Fill climate divisions using provided data dictionary

        Args:
          data (dict): A dictionary of climate division IDs and values
          bins (optional[list]): a list of values for classification
          lblformat (optional[str]): a format specifier to use
          **kwargs (optional): other values
        """
        clidict = load_pickle_geo('climdiv.pickle')
        polygon_fill(self, clidict, data, **kwargs)

    def fill_ugcs(self, data, bins=None, **kwargs):
        """Overlay filled UGC geometries

        The logic for plotting is a bit tricky due to fire zones overlapping
        forecast zones.  In general, provide the zone code if you want it to
        display on top.  Otherwise, I attempt to place forecast zones overtop
        fire weather zones.

        Args:
          data(dict): A dictionary of 6 char UGC code keys and values
          bins(list, optional): Bins to use for cloropleth, default 0:101:10
          plotmissing(bool, optional): Should missing UGC data be plotted?
        """
        if bins is None:
            bins = np.arange(0, 101, 10)
        cmap = stretch_cmap(kwargs.get('cmap'), bins)
        norm = mpcolors.BoundaryNorm(bins, cmap.N)
        # Figure out if we have zones or counties/parishes
        counties = True
        for key in data:
            if key[2] == 'Z':
                counties = False
            break
        ugcs = load_pickle_geo(
            "ugcs_county.pickle" if counties else "ugcs_zone.pickle")
        filter_func = true_filter
        if self.sector == 'state':
            filter_func = state_filter
        elif self.sector == 'cwa':
            filter_func = cwa_filter
        ilabel = kwargs.get('ilabel', False)
        plotmissing = kwargs.get('plotmissing', True)
        for ugc in ugcs:
            ugcdict = ugcs[ugc]
            if not filter_func(self, ugc, ugcdict):
                continue
            if data.get(ugc.decode('utf-8')) is None:
                if not plotmissing:
                    continue
                # Holy cow, it appears values above 300 are always firewx,
                # so lets ignore these when we have no data!
                if not counties and int(ugc[3:]) >= 300:
                    continue
                c = 'white'
                val = '-'
                z = Z_OVERLAY
            else:
                val = data[ugc.decode('utf-8')]
                c = cmap(norm([val, ]))[0]
                z = Z_OVERLAY2
            for polyi, polygon in enumerate(ugcdict.get(b'geom', [])):
                if polygon.exterior is None:
                    continue
                arr = np.asarray(polygon.exterior)
                points = self.ax.projection.transform_points(ccrs.Geodetic(),
                                                             arr[:, 0],
                                                             arr[:, 1])
                p = Polygon(points[:, :2], fc=c, ec='k', zorder=z, lw=.1)
                if z == Z_OVERLAY:
                    self.ax.add_patch(p)
                if z == Z_OVERLAY2:
                    self.ax.add_patch(p)
                if polyi == 0 and ilabel:
                    mx = polygon.centroid.x
                    my = polygon.centroid.y
                    txt = self.ax.text(mx, my, '%s' % (val,), zorder=100,
                                       ha='center', va='center',
                                       transform=ccrs.PlateCarree())
                    txt.set_path_effects([
                            PathEffects.withStroke(linewidth=2,
                                                   foreground="w")])

        if 'cmap' in kwargs:
            del kwargs['cmap']
        self.draw_colorbar(bins, cmap, norm, **kwargs)

    def fill_states(self, data, **kwargs):
        """Add overlay of filled state polygons"""
        states = load_pickle_geo('us_states.pickle')
        polygon_fill(self, states, data, **kwargs)

    def draw_cwas(self, color='k', **kwargs):
        """Overlay CWA Borders

        Draw the CWA border lines on the map.

        Args:
          color(str): The color to draw the CWA borders with
          kwargs(dict, optional): Parameters passed to matplotlib for plotting
        """
        kwargs['edgecolor'] = color
        cwas = load_pickle_geo('cwa.pickle')
        for _a in self.axes:
            _a.add_geometries([val[b'geom']
                               for key, val in cwas.items()],
                              crs=ccrs.PlateCarree(),
                              zorder=Z_POLITICAL,
                              facecolor='None', **kwargs)

    def fill_cwas(self, data, **kwargs):
        """Add overlay of filled polygons for NWS Forecast Offices.

        Method adds a colorized overlay of NWS Forecast Offices based on a
        data dictionary of values provided. This method also places a color
        bar on the image.

        Args:
          data (dict): Dictionary of values with keys representing the 3 char
            or 4 char idenitifer for the WFO.  This assumes the 3 char sites
            are the K ones.
          labels (dict, optional): Optional dictionary that follows the
            ``data`` attribute, but hard codes what should be plotted as a
            label.
          bins (list, optional): List of increasing values to use as bins to
            determine color levels.
          lblformat (str, optional): Format string to use to place labels.
          cmap (matplotlib.cmap, optional): Colormap to use with ``bins``

        """
        cwas = load_pickle_geo('cwa.pickle')
        polygon_fill(self, cwas, data, **kwargs)

    def drawcities(self, minarea=None, labelbuffer=25, textsize=16,
                   color='#000000', outlinecolor='#FFFFFF'):
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
        if minarea is None:
            minarea = 500. if self.sector in ['nws', 'conus'] else 10.
        df2 = df[((df['lat'] > south) & (df['lat'] < north) &
                  (df['lon'] > west) & (df['lon'] < east) &
                  (df['area_km2'] > minarea))]
        # debug option to test an individual point on the plot
        # df2 = df[(df['name'] == 'Sioux City')]
        self.plot_values(df2.lon.values, df2.lat.values, df2.name.values,
                         showmarker=True, labelbuffer=labelbuffer,
                         textsize=textsize, color=color,
                         outlinecolor=outlinecolor)

    def drawcounties(self, color='k'):
        """ Draw counties onto the map

        Args:
          color (color,optional): line color to use
        """
        ugcdict = load_pickle_geo("ugcs_county.pickle")
        polys = []
        for ugc in ugcdict:
            for polygon in ugcdict[ugc].get(b'geom', []):
                polys.append(polygon)
        self.ax.add_geometries(polys, crs=ccrs.PlateCarree(),
                               facecolor='None', edgecolor=color, lw=.4,
                               zorder=Z_POLITICAL)

    def iemlogo(self):
        """Place the IEM Logo"""
        fn = '%s/%s' % (DATADIR, 'logo.png')
        if not os.path.isfile(fn):
            return
        logo = mpimage.imread(fn)
        y0 = self.fig.get_figheight() * 100. - logo.shape[0] - 5
        self.fig.figimage(logo, 5, y0, zorder=3)

    def postprocess(self, view=False, filename=None, web=False,
                    memcache=None, memcachekey=None, memcacheexpire=300,
                    pqstr=None):
        """ postprocess into a slim and trim PNG """
        tmpfn = tempfile.mktemp()
        ram = BytesIO()
        plt.savefig(ram, format='png')
        ram.seek(0)
        im = Image.open(ram)
        im2 = im.convert('RGB').convert('P', palette=Image.ADAPTIVE)
        if memcache and memcachekey:
            ram = BytesIO()
            im2.save(ram, format='png')
            ram.seek(0)
            r = ram.read()
            memcache.set(memcachekey, r, time=memcacheexpire)
            sys.stderr.write("memcached key %s set time %s" % (memcachekey,
                                                               memcacheexpire))
        if web:
            ssw("Content-Type: image/png\n\n")
            im2.save(getattr(sys.stdout, 'buffer', sys.stdout), format='png')
            return
        im2.save(tmpfn, format='PNG')

        if pqstr is not None:
            subprocess.call("/home/ldm/bin/pqinsert -p '%s' %s" % (pqstr,
                                                                   tmpfn),
                            shell=True)
        if view:
            subprocess.call("xv %s" % (tmpfn,), shell=True)
        if filename is not None:
            shutil.copyfile(tmpfn, filename)
        os.unlink(tmpfn)


def windrose(*args, **kwargs):
    """Depreciated."""
    warnings.warn("windrose() is depreciated, use pyiem.windrose_utils!")
    import pyiem.windrose_utils as wru
    return wru.windrose(*args, **kwargs)
