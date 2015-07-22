"""plotting interface
"""
#stdlib
import cStringIO
import tempfile
import os
import sys
import subprocess
import shutil
import datetime
#
from pyiem import reference
from pyiem.datatypes import speed, direction
import pyiem.meteorology as meteorology
# Matplotlib
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib.colors import rgb2hex
from matplotlib.patches import Polygon, Rectangle
import matplotlib.cm as cm
import matplotlib.image as mpimage
import matplotlib.colors as mpcolors
from matplotlib.patches import Wedge
import matplotlib.colorbar as mpcolorbar
import matplotlib.patheffects as PathEffects
from matplotlib.collections import PatchCollection
from matplotlib.artist import Artist
# Basemap
from mpl_toolkits.basemap import Basemap
#
import numpy as np
#
from scipy.interpolate import NearestNDInterpolator
#
from PIL import Image
#
import psycopg2
#
from shapely.wkb import loads

[Z_CF, Z_FILL, Z_CLIP, Z_POLITICAL, Z_OVERLAY] = range(1,6)
DATADIR = os.sep.join([os.path.dirname(__file__), 'data'])


def calendar_plot(sts, ets, data, **kwargs):
    # Figure out how many weeks we have to plot
    weeks = 1
    now = sts
    while now <= ets:
        if now.isoweekday() == 7 and now != sts:
            weeks += 1
        now += datetime.timedelta(days=1)

    # we need 50 pixels per week, 100 dpi
    boxpixelx = 100
    boxpixely = 50
    headerheight = 125
    height = (headerheight + (weeks * boxpixely)) / 100.
    pixelwidth = 20 + boxpixelx * 7
    pixelheight = int(height * 100)

    fig = plt.figure(figsize=(7.2, height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    dx = boxpixelx / float(pixelwidth)
    dy = boxpixely / float(pixelheight)
    offx = 10 / float(pixelwidth)
    offy = 35 / float(pixelheight)
    offx3 = 3 / float(pixelwidth)
    offy3 = 3 / float(pixelheight)

    ax.text(0.5, 0.98, kwargs.get('title', ''), va='center',
            ha='center')

    for i, dow in enumerate(['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']):
        ax.text(offx + dx * i + (dx / 2.), offy + (weeks * dy) + (dy/2.), dow,
                ha='center')

    now = sts
    week = 1
    while now <= ets:
        weekday = now.isoweekday()
        # Sunday
        if weekday == 7:
            weekday = 0
        if weekday == 0 and now != sts:
            week += 1
        # Compute the lower left corner of where we are in the world
        x = offx + weekday * dx
        y = offy + ((weeks - week) * boxpixely) / float(pixelheight)
        color = 'k'
        fmt = '%-d'
        if now.day == 1:
            fmt = '%b %-d'
            color = 'b'
        ax.text(x + offx3, y + dy - offy3, "%s" % (now.strftime(fmt), ),
                transform=ax.transAxes, va='top', color=color)
        val = data.get(now, dict()).get('val')
        if val is not None:
            ax.text(x + offx3 + (dx/2.), y + (dy/2.5) - offy3,
                    val, transform=ax.transAxes, va='center',
                    ha='center', color='k', fontsize=16)

        rect = Rectangle((x, y), dx, dy, zorder=2,
                         facecolor='None', edgecolor='tan')
        ax.add_patch(rect)
        now += datetime.timedelta(days=1)

    return fig


def smooth1d(x, window_len):
    # copied from http://www.scipy.org/Cookbook/SignalSmooth
    s = np.r_[2*x[0] - x[window_len:1:-1], x, 2*x[-1]-x[-1:-window_len:-1]]
    w = np.hanning(window_len)
    y = np.convolve(w/w.sum(), s, mode='same')
    return y[window_len-1:-window_len+1]


def smooth2d(A, sigma=3):

    window_len = max(int(sigma), 3)*2+1
    A1 = np.array([smooth1d(x, window_len) for x in np.asarray(A)])
    A2 = np.transpose(A1)
    A3 = np.array([smooth1d(x, window_len) for x in A2])
    A4 = np.transpose(A3)

    return A4


class BaseFilter(object):

    def prepare_image(self, src_image, dpi, pad):
        ny, nx, depth = src_image.shape
        # tgt_image = np.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src = np.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src[pad:-pad, pad:-pad, :] = src_image[:, :, :]

        return padded_src  # , tgt_image

    def get_pad(self, dpi):
        return 0

    def __call__(self, im, dpi):
        pad = self.get_pad(dpi)
        padded_src = self.prepare_image(im, dpi, pad)
        tgt_image = self.process_image(padded_src, dpi)
        return tgt_image, -pad, -pad


class GrowFilter(BaseFilter):
    "enlarge the area"
    def __init__(self, pixels, color=None):
        self.pixels = pixels
        if color is None:
            self.color = (1, 1, 1)
        else:
            self.color = color

    def __call__(self, im, dpi):
        pad = self.pixels
        ny, nx, depth = im.shape
        new_im = np.empty([pad*2+ny, pad*2+nx, depth], dtype="d")
        alpha = new_im[:, :, 3]
        alpha.fill(0)
        alpha[pad:-pad, pad:-pad] = im[:, :, -1]
        alpha2 = np.clip(smooth2d(alpha, self.pixels/72.*dpi) * 5, 0, 1)
        new_im[:, :, -1] = alpha2
        new_im[:, :, :-1] = self.color
        offsetx, offsety = -pad, -pad

        return new_im, offsetx, offsety


class FilteredArtistList(Artist):
    """
    A simple container to draw filtered artist.
    """
    def __init__(self, artist_list, _filter):
        self._artist_list = artist_list
        self._filter = _filter
        Artist.__init__(self)

    def draw(self, renderer):
        renderer.start_rasterizing()
        renderer.start_filter()
        for a in self._artist_list:
            a.draw(renderer)
        renderer.stop_filter(self._filter)
        renderer.stop_rasterizing()


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


def mask_outside_polygon(poly_verts, ax=None):
    """
    We produce a polygon that lies between the plot border and some interior
    polygon.

    POLY_VERTS is in CCW order, as this is the interior of the polygon
    """
    import matplotlib.patches as mpatches
    import matplotlib.path as mpath

    if ax is None:
        ax = plt.gca()

    # Get current plot limits
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    # Verticies of the plot boundaries in clockwise order
    bound_verts = np.array([(xlim[0], ylim[0]), (xlim[0], ylim[1]),
                            (xlim[1], ylim[1]), (xlim[1], ylim[0]),
                            (xlim[0], ylim[0])])

    # A series of codes (1 and 2) to tell matplotlib whether to draw a lineor
    # move the "pen" (So that there's no connecting line)
    bound_codes = [mpath.Path.MOVETO] + (len(bound_verts) -
                                         1) * [mpath.Path.LINETO]
    poly_codes = [mpath.Path.MOVETO] + (len(poly_verts) -
                                        1) * [mpath.Path.LINETO]

    # Plot the masking patch
    path = mpath.Path(np.concatenate([bound_verts, poly_verts]),
                      bound_codes + poly_codes)
    patch = mpatches.PathPatch(path, facecolor='white', edgecolor='none',
                               zorder=Z_CLIP)
    patch = ax.add_patch(patch)

    # Reset the plot limits to their original extents
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    return patch


def james2():
    """David James suggested color ramp Yellow to Brown"""
    cpool = ['#FFFF80', '#FFEE70', '#FCDD60', '#FACD52', '#F7BE43', '#F5AF36',
             '#E69729', '#CC781F', '#B35915', '#9C400E', '#822507', '#6B0000']
    cmap3 = mpcolors.ListedColormap(cpool, 'james2')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def james():
    """David James suggested color ramp Yellow to Blue """
    cpool = ['#FFFF80', '#CDFA64', '#98F046', '#61E827', '#3BD923', '#3FC453',
             '#37AD7A', '#26989E', '#217AA3', '#215394', '#1B3187', '#0C1078']
    cmap3 = mpcolors.ListedColormap(cpool, 'james')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def whitebluegreenyellowred():
    ''' Rip off NCL's WhiteBlueGreenYellowRed '''
    cpool = ['#cfedfb', '#cdecfb', '#caebfb', '#c7eafa', '#c5e9fa', '#c2e8fa',
             '#bfe7fa', '#bde6fa', '#bae5f9', '#b7e4f9', '#b5e3f9', '#b2e2f9',
             '#b0e1f9', '#ade0f8', '#aadff8', '#a8def8', '#a5ddf8', '#a2dcf7',
             '#9ddaf7', '#9bd8f6', '#98d6f5', '#96d4f3', '#94d2f2', '#92d0f1',
             '#8fcef0', '#8dccee', '#8bcaed', '#88c8ec', '#86c5eb', '#84c3ea',
             '#81c1e8', '#7fbfe7', '#7dbde6', '#7bbbe5', '#78b9e4', '#76b7e2',
             '#74b5e1', '#71b3e0', '#6fb1df', '#6dafdd', '#6aaddc', '#68abdb',
             '#66a9da', '#64a7d9', '#61a5d7', '#5fa3d6', '#5da0d5', '#5a9ed4',
             '#589cd3', '#569ad1', '#5398d0', '#5196cf', '#4f94ce', '#4d92cc',
             '#488eca', '#488fc6', '#4890c3', '#4891bf', '#4892bc', '#4893b8',
             '#4894b5', '#4895b1', '#4896ad', '#4897aa', '#4899a6', '#489aa3',
             '#489b9f', '#489c9c', '#489d98', '#489e94', '#489f91', '#48a08d',
             '#48a18a', '#49a286', '#49a383', '#49a47f', '#49a57c', '#49a678',
             '#49a774', '#49a871', '#49a96d', '#49aa6a', '#49ac66', '#49ad63',
             '#49ae5f', '#49af5b', '#49b058', '#49b154', '#49b251', '#49b34d',
             '#49b546', '#4eb647', '#53b847', '#57b948', '#5cbb48', '#61bc49',
             '#66bd4a', '#6abf4a', '#6fc04b', '#74c14b', '#79c34c', '#7ec44d',
             '#82c64d', '#87c74e', '#8cc84e', '#91ca4f', '#96cb50', '#9acc50',
             '#9fce51', '#a4cf51', '#a9d152', '#add252', '#b2d353', '#b7d554',
             '#bcd654', '#c1d755', '#c5d955', '#cada56', '#cfdc57', '#d4dd57',
             '#d9de58', '#dde058', '#e2e159', '#e7e25a', '#ece45a', '#f0e55b',
             '#f5e75b', '#fae85c', '#fae55b', '#fae159', '#fade58', '#f9da56',
             '#f9d755', '#f9d454', '#f9d052', '#f9cd51', '#f9c950', '#f9c64e',
             '#f9c34d', '#f8bf4b', '#f8bc4a', '#f8b849', '#f8b547', '#f8b246',
             '#f8ae45', '#f8ab43', '#f7a742', '#f7a440', '#f7a03f', '#f79d3e',
             '#f79a3c', '#f7963b', '#f7933a', '#f68f38', '#f68c37', '#f68935',
             '#f68534', '#f68233', '#f67e31', '#f67b30', '#f6782f', '#f5742d',
             '#f5712c', '#f56a29', '#f46829', '#f36629', '#f26429', '#f16229',
             '#f06029', '#ef5e29', '#ef5c29', '#ee5a29', '#ed5829', '#ec5629',
             '#eb5429', '#ea5229', '#e95029', '#e84e29', '#e74c29', '#e64a29',
             '#e54829', '#e44629', '#e44328', '#e34128', '#e23f28', '#e13d28',
             '#e03b28', '#df3928', '#de3728', '#dd3528', '#dc3328', '#db3128',
             '#da2f28', '#d92d28', '#d92b28', '#d82928', '#d72728', '#d62528',
             '#d52328', '#d31f28', '#d11f28', '#cf1e27', '#ce1e27', '#cc1e26',
             '#ca1e26', '#c81d26', '#c71d25', '#c51d25', '#c31d24', '#c11c24',
             '#c01c24', '#be1c23', '#bc1b23', '#ba1b22', '#b91b22', '#b71b22',
             '#b51a21', '#b31a21', '#b21a20', '#b01a20', '#ae191f', '#ac191f',
             '#ab191f', '#a9191e', '#a7181e', '#a5181d', '#a4181d', '#a2171d',
             '#a0171c', '#9e171c', '#9d171b', '#9b161b', '#99161b', '#97161a',
             '#96161a', '#921519']
    cmap3 = mpcolors.ListedColormap(cpool, 'whitebluegreenyellowred')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def maue():
    """ Pretty color ramp Dr Ryan Maue uses """
    cpool = ["#e6e6e6", "#d2d2d2", "#bcbcbc", "#969696", "#646464",
             "#1464d2", "#1e6eeb", "#2882f0", "#3c96f5", "#50a5f5", "#78b9fa",
             "#96d2fa", "#b4f0fa", "#e1ffff",
             "#0fa00f", "#1eb41e", "#37d23c", "#50f050", "#78f573", "#96f58c",
             "#b4faaa", "#c8ffbe",
             "#ffe878", "#ffc03c", "#ffa000", "#ff6000", "#ff3200", "#e11400",
             "#c00000", "#a50000", "#643c32",
             "#785046", "#8c645a", "#b48c82", "#e1beb4", "#f0dcd2", "#ffc8c8",
             "#f5a0a0", "#f5a0a0", "#e16464", "#c83c3c"]

    cmap3 = mpcolors.ListedColormap(cpool, 'maue')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


class MapPlot(object):
    """An object representing a basemap plot.

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
        """ Initializer """
        self.fig = plt.figure(num=None, figsize=figsize,
                              dpi=kwargs.get('dpi', 100))
        self.ax = plt.axes([0.01, 0.05, 0.928, 0.85],
                           axisbg=(0.4471, 0.6235, 0.8117))
        self.cax = plt.axes([0.941, 0.1, 0.058, 0.8], frameon=False,
                            yticks=[], xticks=[])
        self.sector = sector
        self.ak_map = None
        self.ak_ax = None
        self.hi_map = None
        self.hi_ax = None
        self.pr_map = None
        self.pr_ax = None

        if self.sector == 'iowa':
            self.map = Basemap(projection='merc', fix_aspect=False,
                               urcrnrlat=reference.IA_NORTH,
                               llcrnrlat=reference.IA_SOUTH,
                               urcrnrlon=reference.IA_EAST,
                               llcrnrlon=reference.IA_WEST,
                               lat_0=45., lon_0=-92., lat_ts=42.,
                               resolution='i', ax=self.ax)
        elif self.sector == 'dsm':
            self.map = Basemap(projection='merc', fix_aspect=False,
                               urcrnrlat=42.1,
                               llcrnrlat=41.2,
                               urcrnrlon=-93.1,
                               llcrnrlon=-94.2,
                               lat_0=45., lon_0=-92., lat_ts=42.,
                               resolution='i', ax=self.ax)
        elif self.sector == 'ames':
            self.map = Basemap(projection='merc', fix_aspect=False,
                               urcrnrlat=42.085,
                               llcrnrlat=41.965,
                               urcrnrlon=-93.55,
                               llcrnrlon=-93.7,
                               lat_0=45., lon_0=-92., lat_ts=42.,
                               resolution='i', ax=self.ax)
        elif self.sector == 'midwest':
            self.map = Basemap(projection='merc', fix_aspect=False,
                               urcrnrlat=reference.MW_NORTH,
                               llcrnrlat=reference.MW_SOUTH,
                               urcrnrlon=reference.MW_EAST,
                               llcrnrlon=reference.MW_WEST,
                               lat_0=45., lon_0=-92., lat_ts=42.,
                               resolution='i', ax=self.ax)
        elif self.sector == 'custom':
            self.map = Basemap(projection='merc', fix_aspect=False,
                               urcrnrlat=kwargs.get('north'),
                               llcrnrlat=kwargs.get('south'),
                               urcrnrlon=kwargs.get('east'),
                               llcrnrlon=kwargs.get('west'),
                               lat_0=45., lon_0=-92., lat_ts=42.,
                               resolution='i', ax=self.ax)
        elif self.sector == 'north_america':
            self.map = Basemap(llcrnrlon=-145.5, llcrnrlat=1.,
                               urcrnrlon=-2.566, urcrnrlat=46.352,
                               rsphere=(6378137.00, 6356752.3142),
                               resolution='l', area_thresh=1000.,
                               projection='lcc',
                               lat_1=50., lon_0=-107.,
                               ax=self.ax, fix_aspect=False)

        elif self.sector in ['conus', 'nws']:
            self.map = Basemap(projection='stere', lon_0=-105.0, lat_0=90.,
                               lat_ts=60.0,
                               llcrnrlat=23.47, urcrnrlat=45.44,
                               llcrnrlon=-118.67, urcrnrlon=-64.52,
                               rsphere=6371200., resolution='l',
                               area_thresh=10000, ax=self.ax,
                               fix_aspect=False)
            if self.sector == 'nws':
                # Create PR, AK, and HI sectors
                self.pr_ax = plt.axes([0.78,0.055,0.125,0.1], 
                                      axisbg=(0.4471,0.6235,0.8117))
                self.hi_ax = plt.axes([0.56,0.055,0.2,0.1], 
                                      axisbg=(0.4471,0.6235,0.8117))
                self.ak_ax = plt.axes([0.015,0.055,0.2,0.15], 
                                      axisbg=(0.4471,0.6235,0.8117))
                self.pr_map = Basemap(projection='cyl', 
                                      urcrnrlat=18.6, llcrnrlat=17.5, 
                                      urcrnrlon=-65.0, llcrnrlon=-68.0,
                                      resolution='l', ax=self.pr_ax,
                                      fix_aspect=False)
                self.ak_map = Basemap(projection='cyl', 
                                      urcrnrlat=72.1, llcrnrlat=51.08, 
                                      urcrnrlon=-129.0, llcrnrlon=-179.5, 
                                      resolution='l', ax=self.ak_ax,
                                      fix_aspect=False)
                self.hi_map = Basemap(projection='cyl', 
                                      urcrnrlat=22.5, llcrnrlat=18.5, 
                                      urcrnrlon=-154.0, llcrnrlon=-161.0,
                                      resolution='l', ax=self.hi_ax,
                                      fix_aspect=False)

        for _a in [self.map, self.pr_map, self.ak_map, self.hi_map]:
            if _a is None:
                continue
            _a.fillcontinents(color=kwargs.get('axisbg',
                                               (0.4471, 0.6235, 0.8117)),
                              zorder=0)
            _a.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            _a.drawcoastlines(zorder=Z_POLITICAL)

            if 'nostates' not in kwargs:
                _a.drawstates(linewidth=1.5, zorder=Z_OVERLAY,
                              color=kwargs.get('statecolor', 'k'))

        if 'cwas' in kwargs:
            self.drawcwas()
        if not kwargs.get('nologo'):
            self.iemlogo()
        if "title" in kwargs:
            self.fig.text(0.13 if not kwargs.get('nologo') else 0.02, 0.94, kwargs.get("title"), fontsize=18) 
        if "subtitle" in kwargs:
            self.fig.text(0.13 if not kwargs.get('nologo') else 0.02, 0.91, kwargs.get("subtitle") )

        if 'nocaption' not in kwargs:
            self.fig.text(0.01, 0.03, ("%s :: generated %s"
                                       ) % (
                    kwargs.get('caption', 'Iowa Environmental Mesonet'),
                    datetime.datetime.now().strftime("%d %B %Y %I:%M %p %Z"),))

    def close(self):
        ''' Close the figure in the case of batch processing '''
        plt.close()

    def draw_colorbar(self, clevs, cmap, norm, **kwargs):
        """ Create our magic colorbar! """
        
        clevlabels = kwargs.get('clevlabels', clevs)

        under = clevs[0]-(clevs[1]-clevs[0])
        over = clevs[-1]+(clevs[-1]-clevs[-2])
        blevels = np.concatenate([[under,], clevs, [over,]])
        cb2 = mpcolorbar.ColorbarBase(self.cax, cmap=cmap,
                                     norm=norm,
                                     boundaries=blevels,
                                     extend='both',
                                     ticks=None,
                                     spacing='uniform',
                                     orientation='vertical')
        clevstride = int(kwargs.get('clevstride', 1))
        for i, (lev, lbl) in enumerate(zip(clevs, clevlabels)):
            if i % clevstride != 0:
                continue
            y = float(i) / (len(clevs) -1)
            y2 = float(i+1) / (len(clevs) -1)
            dy = (y2-y)/2
            fmt = '%s' if type(lbl) == type('a') else '%g'
            txt = cb2.ax.text(0.5, y, fmt % (lbl,), va='center', ha='center')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                        foreground="w")])
            
        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def plot_station(self, data):
        """Plot values on a map in a station plot like manner

        the positions are a list of 1-9 values, where top row is 1,2,3 and
        then the middle row is 4,5,6 and bottom row is 7,8,9

        Args:
          data (list): list of dicts with station data to plot
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
            (x, y) = self.map(stdata['lon'], stdata['lat'])
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
            if stdata.get('sknt', 0) > 1:
                (u, v) = meteorology.uv(speed(stdata.get('sknt', 0), 'KT'),
                                        direction(stdata.get('drct', 0),
                                                  'DEG'))
                if u is not None and v is not None:
                    self.ax.barbs(x, y, u.value('KT'), v.value('KT'), zorder=1)

            # Sky Coverage
            skycoverage = stdata.get('coverage')
            if skycoverage >= 0 and skycoverage <= 100:
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
                self.ax.annotate("%.0f" % (val, ), xy=(x, y), ha=ha, va=va,
                                 xytext=(offx, offy), color='r',
                                 textcoords="offset points",
                                 clip_on=True)
            # Dew Point
            val = stdata.get('dwpf')
            if val is not None:
                (offx, offy, ha, va) = offsets[7]
                self.ax.annotate("%.0f" % (val, ), xy=(x, y), ha=ha, va=va,
                                 xytext=(offx, offy), color='b',
                                 textcoords="offset points",
                                 clip_on=True)
            # Plot identifier
            val = stdata.get('id')
            if val is not None:
                (offx, offy, ha, va) = offsets[6]
                self.ax.annotate("%s" % (val, ), xy=(x, y), ha=ha, va=va,
                                 xytext=(offx, offy), color='tan',
                                 textcoords="offset points", zorder=1,
                                 clip_on=True, fontsize=8)

    def plot_values(self, lons, lats, vals, fmt='%s', valmask=None,
                    color='#000000', textsize=14, labels=None,
                    labeltextsize=10, labelcolor='#000000'):
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
        """
        if valmask is None:
            valmask = [True] * len(lons)
        if labels is None:
            labels = [''] * len(lons)
        if isinstance(color, str):
            color = [color] * len(lons)
        t = []
        mask = np.zeros(self.fig.canvas.get_width_height(), bool)
        for o, a, v, m, c, l in zip(lons, lats, vals, valmask, color, labels):
            if not m:
                continue
            thismap = self.map
            thisax = self.ax
            if o < -125 and a > 40 and self.ak_map is not None:
                thismap = self.ak_map
                thisax = self.ak_ax
            elif o < -125 and a < 40 and self.hi_map is not None:
                thismap = self.hi_map
                thisax = self.hi_ax

            # compute the pixel coordinate of this data point
            (x, y) = thismap(o, a)
            (imgx, imgy) = thisax.transData.transform([x, y])
            imgx = int(imgx)
            imgy = int(imgy)

            # Our text is centered, so we can make some approximations on the
            # bounding box size it will fill, we have to do it this way as
            # waiting for rendering is too late, we picked 0.7 out of a hat
            # as it appears to be a good approx
            mystr = fmt % (v,)
            bwidth = len(mystr) * textsize
            _cnt = np.sum(np.where(mask[imgx-bwidth/2:imgx+bwidth/2,
                                        imgy-textsize:imgy+textsize], 1, 0))
            # If we have more than 15 pixels of overlap, don't plot this!
            if _cnt > 15:
                continue
            # Useful for debugging this algo
            # rec = plt.Rectangle((imgx-bwidth/2, imgy-textsize),
            #                    bwidth, textsize*2, transform=None,
            #                    facecolor='None', edgecolor='k')
            # thisax.add_patch(rec)
            mask[imgx-textsize:imgx+textsize,
                 imgy-textsize:imgy+textsize] = True
            t0 = thisax.text(x, y, mystr, color=c,
                             size=textsize, zorder=Z_OVERLAY+2,
                             va='center', ha='center')
            t0.set_clip_on(True)
            t.append(t0)

            if l and l != '':
                thisax.annotate("%s" % (l, ), xy=(x, y), ha='center',
                                va='top',
                                xytext=(0, 0 - textsize/2),
                                color=labelcolor,
                                textcoords="offset points",
                                zorder=Z_OVERLAY+1,
                                clip_on=True, fontsize=labeltextsize)

        if len(t) > 0:
            white_glows = FilteredArtistList(t, GrowFilter(3))
            thisax.add_artist(white_glows)
            white_glows.set_zorder(t[0].get_zorder()-0.1)

    def scatter(self, lons, lats, vals, clevs, **kwargs):
        """ Plot scatter points with some colorized symbology """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        colors = cmap( norm(vals) )
        x,y = self.map(lons, lats)
        self.ax.scatter(x, y, c=colors, edgecolors=colors)
        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(clevs, cmap, norm, **kwargs)

    def hexbin(self, lons, lats, vals, clevs, **kwargs):
        """ hexbin wrapper """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        
        x, y = self.map(lons, lats)
        self.map.hexbin(x, y, C=vals, norm=norm,
                               cmap=cmap, zorder=Z_FILL)
        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(clevs, cmap, norm, **kwargs)

        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def pcolormesh(self, lons, lats, vals, clevs, **kwargs):
        """ pcolormesh wrapper """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        
        self.map.pcolormesh(lons, lats, vals, norm=norm,
                               cmap=cmap, zorder=Z_FILL, latlon=True)

        if kwargs.get("clip_on", True):
            self.draw_mask()
        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(clevs, cmap, norm, **kwargs)

        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def draw_mask(self):
        ''' Draw the mask, when appropriate '''
        # can't mask what we don't know
        if self.sector not in ('midwest', 'conus', 'iowa'):
            return
        # in lon,lat
        ccw = load_bounds('%s_ccw' % (self.sector,))
        # in map coords
        x,y = self.map(ccw[:,0], ccw[:,1])
        mask_outside_polygon(zip(x,y), ax=self.ax)

    def contourf(self, lons, lats, vals, clevs, **kwargs):
        """ Contourf """
        if type(lons) == type([]):
            lons = np.array( lons )
            lats = np.array( lats )
            vals = np.array( vals )
        if vals.ndim == 1:
            # We need to grid, get current plot bounds in display proj
            # Careful here as a rotated projection may have maxes not in ul
            xbnds = self.ax.get_xlim()
            ybnds = self.ax.get_ylim()
            ll = self.map(xbnds[0], ybnds[0], inverse=True)
            ul = self.map(xbnds[0], ybnds[1], inverse=True)
            ur = self.map(xbnds[1], ybnds[1], inverse=True)
            lr = self.map(xbnds[1], ybnds[0], inverse=True)
            maxy = max(ul[1], ur[1])
            miny = min(ll[1], ul[1])
            maxx = max(lr[0], ur[0])
            minx = min(ll[0], ul[0])
            xi = np.linspace(minx, maxx, 100)
            yi = np.linspace(miny, maxy, 100)
            xi, yi = np.meshgrid(xi, yi)
            #vals = griddata( zip(lons, lats), vals, (xi, yi) , 'cubic')
            #rbfi = Rbf(lons, lats, vals, function='cubic')
            nn = NearestNDInterpolator((lons, lats), vals)
            vals = nn(xi, yi)
            #vals = rbfi(xi, yi)
            lons = xi
            lats = yi
        if lons.ndim == 1:
            lons, lats = np.meshgrid(lons, lats)
        
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
                
        x, y = self.map(lons, lats)
        from scipy.signal import convolve2d
        window = np.ones((6, 6))
        vals = convolve2d(vals, window / window.sum(), mode='same', 
                          boundary='symm')
        #vals = maskoceans(lons, lats, vals, resolution='h')
        self.map.contourf(x, y, vals, clevs,
                          cmap=cmap, norm=norm, zorder=Z_FILL, extend='both')
        self.draw_mask()
        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(clevs, cmap, norm, **kwargs)

        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def fill_climdiv(self, data, 
                    shapefile='/mesonet/data/gis/static/shape/4326/nws/0.01/climdiv',
                  bins=np.arange(0,101,10),
                  lblformat='%.0f', **kwargs):
        fn = '/mesonet/data/gis/static/shape/4326/nws/0.01/climdiv.shp'
        if not os.path.isfile(fn):
            return
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(bins, cmap.N)
        #m = cm.get_cmap('jet')
        self.map.readshapefile(shapefile, 'climdiv', ax=self.ax)
        plotted = []
        for nshape, seg in enumerate(self.map.climdiv):
            state = self.map.climdiv_info[nshape]['ST_ABBRV']
            thismap = self.map
            thisax = self.ax
            transform = False
            if state in ['AK',]:
                if self.ak_map is None:
                    continue
                thismap = self.ak_map
                thisax = self.ak_ax
                transform = True
            elif state in ['HI']:
                if self.hi_map is None:
                    continue
                thismap = self.hi_map
                thisax = self.hi_ax
                transform = True
            elif state in ['PR',]:
                if self.pr_map is None:
                    continue
                thismap = self.pr_map
                thisax = self.pr_ax
                transform = True
            clidiv = "%sC0%s" % (state, 
                                  self.map.climdiv_info[nshape]['CD_2DIG'])
            if clidiv not in data:
                continue
            val = data.get(clidiv)
            c = cmap(norm([val, ]))[0]
            # Check area in meters... 100,000 x 100,000
            if clidiv not in plotted:
                seg = np.array( seg )
                mx =  (np.max(seg[:,0]) + np.min(seg[:,0])) / 2.0
                my =  (np.max(seg[:,1]) + np.min(seg[:,1])) / 2.0
                txt = thisax.text(mx, my, lblformat % (val,), zorder=100,
                         ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                         foreground="w")])
                plotted.append( clidiv )
            if transform:
                seg = np.array( seg )
                xx, yy = self.map( seg[:,0], seg[:,1] , inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)

            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)

        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(bins, cmap, norm, **kwargs)

    def fill_ugc_counties(self, data, bins=np.arange(0, 101, 10), **kwargs):
        """ Fill UGC counties based on the data dict provided, please """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(bins, cmap.N)

        pgconn = psycopg2.connect(database='postgis', host='iemdb',
                                  user='nobody')
        cursor = pgconn.cursor()

        cursor.execute("""
        SELECT ugc, ST_asEWKB(simple_geom) from ugcs WHERE end_ts is null
        and substr(ugc,3,1) = 'C'
        """)
        akpatches = []
        hipatches = []
        prpatches = []
        patches = []
        for row in cursor:
            ugc = row[0]
            if data.get(ugc) is None:
                c = 'white'
            else:
                c = cmap(norm([data[ugc], ]))[0]
            geom = loads(str(row[1]))
            for polygon in geom:
                if polygon.exterior is None:
                    continue
                a = np.asarray(polygon.exterior)
                if ugc[:2] == 'AK':
                    if self.ak_ax is None:
                        continue
                    (x, y) = self.ak_map(a[:, 0], a[:, 1])
                    a = zip(x, y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    akpatches.append(p)
                elif ugc[:2] == 'HI':
                    if self.hi_ax is None:
                        continue
                    (x, y) = self.hi_map(a[:, 0], a[:, 1])
                    a = zip(x, y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    hipatches.append(p)
                elif ugc[:2] == 'PR':
                    if self.pr_ax is None:
                        continue
                    (x, y) = self.pr_map(a[:, 0], a[:, 1])
                    a = zip(x, y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    prpatches.append(p)
                else:
                    (x, y) = self.map(a[:, 0], a[:, 1])
                    a = zip(x, y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    patches.append(p)

        if len(patches) > 0:
            self.ax.add_collection(
                        PatchCollection(patches, match_original=True))
        if len(akpatches) > 0 and self.ak_ax is not None:
            self.ak_ax.add_collection(
                        PatchCollection(akpatches, match_original=True))
        if len(hipatches) > 0 and self.hi_ax is not None:
            self.hi_ax.add_collection(
                        PatchCollection(hipatches, match_original=True))
        if len(prpatches) > 0 and self.pr_ax is not None:
            self.pr_ax.add_collection(
                        PatchCollection(prpatches, match_original=True))
        if 'cmap' in kwargs:
            del kwargs['cmap']
        self.draw_colorbar(bins, cmap, norm, **kwargs)

    def fill_states(self, data, 
                    shapefile='/mesonet/data/gis/static/shape/4326/nws/0.01/states',
                  bins=np.arange(0,101,10),
                  lblformat='%.0f', **kwargs):
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(bins, cmap.N)
        
        self.map.readshapefile(shapefile, 'states', ax=self.ax)
        plotted = []
        for nshape, seg in enumerate(self.map.states):
            state = self.map.states_info[nshape]['STATE']
            thismap = self.map
            thisax = self.ax
            transform = False
            if state in ['AK',]:
                if self.ak_map is None:
                    continue
                thismap = self.ak_map
                thisax = self.ak_ax
                transform = True
            elif state in ['HI']:
                if self.hi_map is None:
                    continue
                thismap = self.hi_map
                thisax = self.hi_ax
                transform = True
            elif state in ['PR',]:
                if self.pr_map is None:
                    continue
                thismap = self.pr_map
                thisax = self.pr_ax
                transform = True
            if not data.has_key( state ):
                continue
            val = data.get( state )
            c = cmap( norm([val,]) )[0]
            # Check area in meters... 100,000 x 100,000
            if state not in plotted:
                mx, my = thismap(self.map.states_info[nshape]['LON'],
                                  self.map.states_info[nshape]['LAT'])
                txt = thisax.text(mx, my, lblformat % (val,), zorder=100,
                         ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                         foreground="w")])
                plotted.append( state )
            if transform:
                seg = np.array( seg )
                xx, yy = self.map( seg[:,0], seg[:,1] , inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)
                
            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)
        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(bins, cmap, norm, **kwargs)

    def fill_cwas(self, data, labels={},
                  shapefile='/mesonet/data/gis/static/shape/4326/nws/0.01/cwas',
                  bins=np.arange(0, 101, 10),
                  lblformat='%.0f', cmap=None, **kwargs):
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
          shapefile (str, optional): Location of a CWA shapefile to use for
            plotting.  Defaults to one provided by IEM code.
          bins (list, optional): List of increasing values to use as bins to
            determine color levels.
          lblformat (str, optional): Format string to use to place labels.
          cmap (matplotlib.cmap, optional): Colormap to use with ``bins``

        """
        fn = '/mesonet/data/gis/static/shape/4326/nws/0.01/cwas.shp'
        if not os.path.isfile(fn):
            return
        if 'JSJ' in data:
            data['SJU'] = data['JSJ']
        if cmap is None:
            cmap = maue()
        norm = mpcolors.BoundaryNorm(bins, cmap.N)

        self.map.readshapefile(shapefile, 'cwas', ax=self.ax)
        plotted = []
        for nshape, seg in enumerate(self.map.cwas):
            cwa = self.map.cwas_info[nshape]['CWA']
            thismap = self.map
            thisax = self.ax
            transform = False
            if cwa not in data:
                continue
            if cwa in ['AFC', 'AFG', 'AJK']:
                if self.ak_map is None:
                    continue
                thismap = self.ak_map
                thisax = self.ak_ax
                transform = True
            elif cwa in ['HFO', 'PPG']:
                if self.hi_map is None:
                    continue
                thismap = self.hi_map
                thisax = self.hi_ax
                transform = True
            elif cwa in ['JSJ', 'SJU']:
                if self.pr_map is None:
                    continue
                thismap = self.pr_map
                thisax = self.pr_ax
                transform = True
            val = data.get(cwa)
            c = cmap(norm([float(val), ]))[0]
            # Check area in meters... 100,000 x 100,000
            if self.map.cwas_info[nshape]['CWA'] not in plotted:
                mx, my = thismap(float(self.map.cwas_info[nshape]['LON']),
                                 float(self.map.cwas_info[nshape]['LAT']))
                txt = thisax.text(mx, my, lblformat % (labels.get(cwa, val),),
                                  zorder=100, ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2,
                                                             foreground="w")])
                plotted.append(cwa)
            if transform:
                seg = np.array(seg)
                # convert read shapefile back into lat / lon
                xx, yy = self.map(seg[:, 0], seg[:, 1], inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)

            poly = Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)
        if 'cmap' in kwargs:
            del kwargs['cmap']
        self.draw_colorbar(bins, cmap, norm, **kwargs)

    def drawcwas(self):
        ''' Draw CWAS '''
        fn = '/mesonet/data/gis/static/shape/4326/nws/cwas.shp'
        if not os.path.isfile(fn):
            return
        self.map.readshapefile(fn[:-4], 'c')
        for nshape, seg in enumerate(self.map.c):
            poly=Polygon(seg, fill=False, ec='k', lw=.8, zorder=Z_POLITICAL)
            self.ax.add_patch(poly)

    def drawcounties(self, color='k'):
        """ Draw counties onto the map (only Iowa at this time)

        Args:
          color (color,optional): line color to use

        """
        self.map.readshapefile('/mesonet/data/gis/static/shape/4326/iowa/iacounties', 'c')
        for nshape, seg in enumerate(self.map.c):
            poly = Polygon(seg, fill=False, ec=color, lw=.4,
                           zorder=Z_POLITICAL)
            self.ax.add_patch(poly)

    def iemlogo(self):
        """ Draw a logo """
        fn = '%s/%s' % (DATADIR, 'logo.png')
        if not os.path.isfile(fn):
            return
        logo = Image.open(fn)
        ax3 = plt.axes([0.02, 0.89, 0.1, 0.1], frameon=False,
                       axisbg=(0.4471, 0.6235, 0.8117), yticks=[], xticks=[])
        ax3.imshow(logo, origin='upper')

    def make_colorbar(self, bins, colorramp):
        """ Manual Color Bar """
        ax = plt.axes([0.92, 0.1, 0.07, 0.8], frameon=False,
                      yticks=[], xticks=[])
        colors = []
        for i in range(len(bins)):
            colors.append( rgb2hex(colorramp(i)) )
            txt = ax.text(0.5, i, "%s" % (bins[i],), ha='center', va='center',
                          color='w')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                     foreground="k")])
        ax.barh(np.arange(len(bins)), [1]*len(bins), height=1,
                color=colorramp(range(len(bins))),
                ec='None')
        
    def makefeature(self):
        """ Special workflow for feature generation """
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        bigfn = "%s.png" % (tomorrow.strftime("%y%m%d"),)
        littlefn = "%s_s.png" % (tomorrow.strftime("%y%m%d"),)
        
        plt.savefig(bigfn, dpi=100)
        plt.savefig(littlefn, dpi=34)
        
    def postprocess(self, view=False, filename=None, web=False,
                    memcache=None, memcachekey=None, memcacheexpire=300,
                    pqstr=None):
        """ postprocess into a slim and trim PNG """
        tmpfn = tempfile.mktemp()
        ram = cStringIO.StringIO()
        plt.savefig(ram, format='png')
        ram.seek(0)
        im = Image.open(ram)
        im2 = im.convert('RGB').convert('P', palette=Image.ADAPTIVE)
        if memcache and memcachekey:
            ram = cStringIO.StringIO()
            im2.save( ram, format='png')
            ram.seek(0)
            r = ram.read()
            memcache.set(memcachekey, r, time=memcacheexpire)
            sys.stderr.write("memcached key %s set time %s" % (memcachekey,
                                                    memcacheexpire))
        if web:
            print "Content-Type: image/png\n"
            im2.save( sys.stdout, format='png' )
            return
        im2.save( tmpfn , format='PNG')
        
        if pqstr is not None:
            subprocess.call("/home/ldm/bin/pqinsert -p '%s' %s" % (pqstr, 
                                                                   tmpfn), 
                    shell=True)
        if view:
            subprocess.call("xv %s" % (tmpfn,), shell=True)
        if filename is not None:
            shutil.copyfile(tmpfn, filename)
        os.unlink(tmpfn)


def windrose(station, database='asos', fp=None, months=np.arange(1, 13),
             hours=np.arange(0, 24), sts=datetime.datetime(1970, 1, 1),
             ets=datetime.datetime(2050, 1, 1), units="mph", nsector=36,
             justdata=False):
    """Utility function that generates a windrose plot

    Args:
      station (str): station identifier to search database for
      database (str,optional): database name to look for data within
      fp (str,optional): filename to write the image to, if it is `None` then
        write to stdout (aka web server)
      months (list,optional): optional list of months to limit plot to
      hours (list,optional): optional list of hours to limit plot to
      sts (datetime,optional): start datetime
      ets (datetime,optional): end datetime
      units (str,optional): units to plot values as
      nsector (int,optional): number of bins to devide the windrose into
      justdata (boolean,optional): if True, write out the data only
    """
    from windrose import WindroseAxes
    from windrose.windrose import histogram
    windunits = {
        'mph': {'label': 'miles per hour', 'dbmul': 1.15,
                'bins': (0, 2, 5, 7, 10, 15, 20), 'abbr': 'mph',
                'binlbl': ('2-5', '5-7', '7-10', '10-15', '15-20', '20+')},
        'kts': {'label': 'knots', 'dbmul': 1.0,
                'bins': (0, 2, 5, 7, 10, 15, 20), 'abbr': 'kts',
                'binlbl': ('2-5', '5-7', '7-10', '10-15', '15-20', '20+')},
        'mps': {'label': 'meters per second', 'dbmul': 0.5144,
                'bins': (0, 2, 4, 6, 8, 10, 12), 'abbr': 'm s$^{-1}$',
                'binlbl': ('2-4', '4-6', '6-8', '8-10', '10-12', '12+')},
        'kph': {'label': 'kilometers per hour', 'dbmul': 1.609,
                'bins': (0, 4, 10, 14, 20, 30, 40), 'abbr': '$km h^{-1}$',
                'binlbl': ('4-10', '10-14', '14-20', '20-30', '30-40', '40+')},
    }

    # Query metadata
    db = psycopg2.connect(database='mesosite', host='iemdb', user='nobody')
    mcursor = db.cursor()
    mcursor.execute("""SELECT name from stations where id = %s""", (station,))
    row = mcursor.fetchall()
    if len(row) == 0:
        sname = "((%s))" % (station,)
    else:
        sname = row[0][0]
    mcursor.close()
    db.close()

    monthLimiter = ""
    month_limit_text = "All included"
    if len(months) == 1:
        monthLimiter = "and extract(month from valid) = %s" % (months[0],)
        month_limit_text = str(tuple(months))
    elif len(months) < 12:
        monthLimiter = "and extract(month from valid) in %s" % (
                                    (str(tuple(months))).replace("'", ""),)
        month_limit_text = str(tuple(months))

    hour_limit_text = "All included"
    hourLimiter = ""
    if len(hours) == 1:
        hourLimiter = "and extract(hour from valid) = %s" % (hours[0],)
        hour_limit_text = str(tuple(hours))
    elif len(hours) < 24:
        hourLimiter = "and extract(hour from valid) in %s" % (
                                    (str(tuple(hours))).replace("'", ""),)
        hour_limit_text = str(tuple(hours))

    # Query observations
    db = psycopg2.connect(database=database, host='iemdb', user='nobody')
    acursor = db.cursor()
    sql = """SELECT sknt, drct, valid from alldata WHERE station = '%s'
        and valid > '%s' and valid < '%s'
        %s
        %s """ % (station, sts, ets, monthLimiter, hourLimiter)
    acursor.execute(sql)
    sped = np.zeros((acursor.rowcount,), 'f')
    drct = np.zeros((acursor.rowcount,), 'f')
    i = 0
    for row in acursor:
        # if row[2].month not in months or row[2].hour not in hours:
        #    continue
        if i == 0:
            minvalid = row[2]
            maxvalid = row[2]
        if row[2] < minvalid:
            minvalid = row[2]
        if row[2] > maxvalid:
            maxvalid = row[2]
        if row[0] is None or row[0] < 3 or row[1] is None or row[1] < 0:
            sped[i] = 0
            drct[i] = 0
        elif row[0] == 0 or row[1] == 0:
            sped[i] = 0
            drct[i] = 0
        else:
            sped[i] = row[0] * windunits[units]['dbmul']
            drct[i] = row[1]
        i += 1

    acursor.close()
    db.close()
    if i < 5 or max(sped) == 0:
        _ = plt.figure(figsize=(6, 7), dpi=80, facecolor='w', edgecolor='w')
        label = 'Not enough data available to generate plot'
        plt.gcf().text(0.17, 0.89, label)
        if fp is not None:
            plt.savefig(fp)
        else:
            print "Content-Type: image/png\n"
            plt.savefig(sys.stdout, format='png')
        return

    if justdata:
        sys.stdout.write('Content-type: text/plain\n\n')
        dir_edges, var_bins, table = histogram(drct, sped,
                                        np.asarray(windunits[units]['bins']), 
                                        nsector, normed=True)
        sys.stdout.write(("# Windrose Data Table (Percent Frequency) "
                          +"for %s (%s)\n") % (sname, station))
        sys.stdout.write("# Observation Count: %s\n" % (len(sped),))
        sys.stdout.write("# Period: %s - %s\n" % (minvalid.strftime("%-d %b %Y"),
                                                  maxvalid.strftime("%-d %b %Y")
                                                  ))
        sys.stdout.write("# Hour Limiter: %s\n" % (hour_limit_text,))
        sys.stdout.write("# Month Limiter: %s\n" % (month_limit_text,))
        sys.stdout.write("# Wind Speed Units: %s\n" % (
                                                windunits[units]['label'],))
        sys.stdout.write("# Generated %s UTC, contact: akrherz@iastate.edu\n" % (
                    datetime.datetime.utcnow().strftime("%d %b %Y %H:%M"),))
        sys.stdout.write("# First value in table is CALM\n")
        sys.stdout.write("       ,")
        for j in range(len(var_bins)-1):
            sys.stdout.write(" %4.1f-%4.1f," % (var_bins[j], var_bins[j+1]-0.1))
        sys.stdout.write("\n")
        dir_edges2 = np.concatenate((np.array(dir_edges), 
                            [dir_edges[-1] + (dir_edges[-1] - dir_edges[-2]),]))
        for i in range(len(dir_edges2)-1):
            sys.stdout.write("%03i-%03i," % (dir_edges2[i], dir_edges2[i+1]))
            for j in range(len(var_bins)-1):
                sys.stdout.write(" %9.3f," % (table[j,i],))
            sys.stdout.write("\n")
        return

    # Generate figure
    fig = plt.figure(figsize=(6, 7), dpi=80, facecolor='w', edgecolor='w')
    rect = [0.1, 0.1, 0.8, 0.8]
    ax = WindroseAxes(fig, rect, axisbg='w')
    fig.add_axes(ax)
    ax.bar(drct, sped, normed=True, bins=windunits[units]['bins'], opening=0.8, 
           edgecolor='white', nsector=nsector)
    handles = []
    for p in ax.patches_list:
        color = p.get_facecolor()
        handles.append( plt.Rectangle((0, 0), 0.1, 0.3,
                    facecolor=color, edgecolor='black'))
    l = fig.legend(handles, windunits[units]['binlbl'] , loc=3,
                   ncol=6, title='Wind Speed [%s]' % (windunits[units]['abbr'],), 
                   mode=None, columnspacing=0.9, handletextpad=0.45)
    plt.setp(l.get_texts(), fontsize=10)
    # Now we put some fancy debugging info on the plot
    tlimit = "Time Domain: "
    if len(hours) == 24 and len(months) == 12:
        tlimit = "All Year"
    if len(hours) < 24:
        if len(hours) > 4:
            tlimit += "%s-%s" % (
                    datetime.datetime(2000, 1, 1, hours[0]).strftime("%-I %p"),
                    datetime.datetime(2000, 1, 1, hours[-1]).strftime("%-I %p")
                                 )
        else:
            for h in hours:
                tlimit += "%s," % (
                            datetime.datetime(2000, 1, 1, h).strftime("%-I %p"),)
    if len(months) < 12:
        for h in months:
            tlimit += "%s," % (datetime.datetime(2000,h,1).strftime("%b"),)
    label = """[%s] %s
Windrose Plot [%s]
Period of Record: %s - %s
Obs Count: %s Calm: %.1f%% Avg Speed: %.1f %s""" % (station, sname, tlimit,
                                                    minvalid.strftime("%d %b %Y"), maxvalid.strftime("%d %b %Y"), 
        np.shape(sped)[0], 
        np.sum( np.where(sped < 2., 1., 0.)) / np.shape(sped)[0] * 100.,
        np.average(sped), windunits[units]['abbr'])
    plt.gcf().text(0.17, 0.89, label)
    plt.gcf().text(0.01, 0.1, "Generated: %s" % (
                   datetime.datetime.now().strftime("%d %b %Y"),),
                   verticalalignment="bottom")
    # Make a logo
    im = mpimage.imread('%s/%s' % (DATADIR, 'logo.png'))

    plt.figimage(im, 10, 625)

    if fp is not None:
        plt.savefig(fp)
    else:
        sys.stdout.write("Content-Type: image/png\n\n")
        plt.savefig(sys.stdout, format='png')

    del sped, drct, im
