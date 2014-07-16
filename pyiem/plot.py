"""
  OO interface to properly generate fancy pants IEM plots

Like it or not, we care about zorder!

  z
  1 Continent fill
  2 contour or fill
  3 polygon clipping
  4 states
  5 overlay text
"""
[Z_CF, Z_FILL, Z_CLIP, Z_POLITICAL, Z_OVERLAY] = range(1,6)

import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
from matplotlib.colors import rgb2hex
from matplotlib.patches import Polygon
import matplotlib.cm as cm
import matplotlib.colors as mpcolors
import matplotlib.colorbar as mpcolorbar
import matplotlib.patheffects as PathEffects
from matplotlib.collections import PatchCollection
import mx.DateTime
import numpy as np
from scipy.interpolate import NearestNDInterpolator
from pyiem import reference
from PIL import Image
import cStringIO
import tempfile
import os
import sys
import subprocess
import shutil
import datetime
import psycopg2
from shapely.wkb import loads


DATADIR = os.sep.join([os.path.dirname(__file__), 'data'])

from matplotlib.artist import Artist

def smooth1d(x, window_len):
    # copied from http://www.scipy.org/Cookbook/SignalSmooth

    s=np.r_[2*x[0]-x[window_len:1:-1],x,2*x[-1]-x[-1:-window_len:-1]]
    w = np.hanning(window_len)
    y=np.convolve(w/w.sum(),s,mode='same')
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
        #tgt_image = np.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src = np.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src[pad:-pad, pad:-pad,:] = src_image[:,:,:]

        return padded_src#, tgt_image

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
            self.color=(1, 1, 1)
        else:
            self.color=color

    def __call__(self, im, dpi):
        pad = self.pixels
        ny, nx, depth = im.shape
        new_im = np.empty([pad*2+ny, pad*2+nx, depth], dtype="d")
        alpha = new_im[:,:,3]
        alpha.fill(0)
        alpha[pad:-pad, pad:-pad] = im[:,:,-1]
        alpha2 = np.clip(smooth2d(alpha, self.pixels/72.*dpi) * 5, 0, 1)
        new_im[:,:,-1] = alpha2
        new_im[:,:,:-1] = self.color
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

def load_bounds(filename):
    """
    Load the boundary file into a [np array]
    """
    return np.load("%s/%s.npy" % (DATADIR, filename))

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
    bound_verts = np.array( [(xlim[0], ylim[0]), (xlim[0], ylim[1]),
                   (xlim[1], ylim[1]), (xlim[1], ylim[0]),
                   (xlim[0], ylim[0])] )

    # A series of codes (1 and 2) to tell matplotlib whether to draw a lineor
    # move the "pen" (So that there's no connecting line)
    bound_codes = [mpath.Path.MOVETO] + (len(bound_verts) - 1) *[mpath.Path.LINETO]
    poly_codes = [mpath.Path.MOVETO] + (len(poly_verts) - 1) *[mpath.Path.LINETO]

    # Plot the masking patch
    path = mpath.Path(np.concatenate([bound_verts,poly_verts]), bound_codes + poly_codes)
    patch = mpatches.PathPatch(path, facecolor='white', edgecolor='none', 
                               zorder=Z_CLIP)
    patch = ax.add_patch(patch)

    # Reset the plot limits to their original extents
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    return patch

def james2():
    ''' David James suggested color ramp Yellow to Brown
    
255, 255, 128
255, 238, 112
252, 221,  96
250, 205,  82
247, 190,  67
245, 175,  54
230, 151,  41
204, 120,  31
179,  89,  21
156,  64,  14
130,  37,   7
107,   0,   0
    
     '''
    cpool = ['#FFFF80', '#FFEE70', '#FCDD60', '#FACD52', '#F7BE43', '#F5AF36',
             '#E69729', '#CC781F', '#B35915', '#9C400E', '#822507', '#6B0000']
    cmap3 = mpcolors.ListedColormap(cpool, 'james2')
    cmap3.set_over("#000000")
    cmap3.set_under("#FFFFFF")
    cmap3.set_bad("#FFFFFF")
    cm.register_cmap(cmap=cmap3)
    return cmap3


def james():
    ''' David James suggested color ramp Yellow to Blue 
255, 255, 128
205, 250, 100
152, 240,  70
 97, 232,  39
 59, 217,  35
 63, 196,  83
 55, 173, 122
 38, 152, 158
 33, 122, 163
 33,  83, 148
 27,  49, 135
 12,  16, 120
    
    '''
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

class MapPlot:
    
    def __init__(self, sector='iowa', figsize=(10.24,7.68), **kwargs):
        """ Initializer """
        self.fig = plt.figure(num=None, figsize=figsize )
        self.fig.subplots_adjust(bottom=0, left=0, right=1, top=1, wspace=0, 
                                 hspace=0)
        self.ax = plt.axes([0.01,0.05,0.928,0.85], axisbg=(0.4471,0.6235,0.8117))
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
            """ Standard view for Iowa """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=reference.IA_NORTH, 
                           llcrnrlat=reference.IA_SOUTH, 
                           urcrnrlon=reference.IA_EAST, 
                           llcrnrlon=reference.IA_WEST, 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
        elif self.sector == 'dsm':
            """ Zoomed in for Ames """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=42.1, 
                           llcrnrlat=41.2, 
                           urcrnrlon=-93.1, 
                           llcrnrlon=-94.2, 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
        elif self.sector == 'ames':
            """ Zoomed in for DSM """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=42.085, 
                           llcrnrlat=41.965, 
                           urcrnrlon=-93.55, 
                           llcrnrlon=-93.7, 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
        elif self.sector == 'midwest':
            """ Standard view for Iowa """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=reference.MW_NORTH, 
                           llcrnrlat=reference.MW_SOUTH, 
                           urcrnrlon=reference.MW_EAST, 
                           llcrnrlon=reference.MW_WEST, 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
            self.map.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            self.map.drawcoastlines(zorder=Z_POLITICAL)
        elif self.sector == 'custom':
            """ Custom view """
            self.map = Basemap(projection='merc', fix_aspect=False,
                           urcrnrlat=kwargs.get('north'), 
                           llcrnrlat=kwargs.get('south'), 
                           urcrnrlon=kwargs.get('east'), 
                           llcrnrlon=kwargs.get('west'), 
                           lat_0=45.,lon_0=-92.,lat_ts=42.,
                           resolution='i', ax=self.ax)
            self.map.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            self.map.drawcoastlines(zorder=Z_POLITICAL)
        elif self.sector == 'north_america':
            self.map = Basemap(llcrnrlon=-145.5,llcrnrlat=1.,urcrnrlon=-2.566,
                               urcrnrlat=46.352,
                               rsphere=(6378137.00,6356752.3142),
                               resolution='l',area_thresh=1000.,projection='lcc',
                               lat_1=50.,lon_0=-107.,
                               ax=self.ax, fix_aspect=False)
            self.map.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            self.map.drawcoastlines(zorder=Z_POLITICAL)           
        elif self.sector in ['conus', 'nws']:
            self.map = Basemap(projection='stere',lon_0=-105.0,lat_0=90.,
                            lat_ts=60.0,
                            llcrnrlat=23.47,urcrnrlat=45.44,
                            llcrnrlon=-118.67,urcrnrlon=-64.52,
                            rsphere=6371200.,resolution='l',area_thresh=10000,
                            ax=self.ax,
                                      fix_aspect=False)
            self.map.drawcountries(linewidth=1.0, zorder=Z_POLITICAL)
            self.map.drawcoastlines(zorder=Z_POLITICAL)
            if self.sector == 'nws':
                """ Create PR, AK, and HI sectors """
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
        
        if self.pr_map:
            self.pr_map.fillcontinents(color='0.7',zorder=0)
        if self.ak_map:
            self.ak_map.fillcontinents(color='0.7',zorder=0)
        if self.hi_map:
            self.hi_map.fillcontinents(color='0.7',zorder=0)
        self.map.fillcontinents(color='0.7', zorder=0) # Read docs on 0 meaning

        if not kwargs.has_key('nostates'):
            self.map.drawstates(linewidth=1.5, zorder=Z_OVERLAY, ax=self.ax)
        if kwargs.has_key('cwas'):
            self.drawcwas()
        if not kwargs.get('nologo'):
            self.iemlogo()
        if kwargs.has_key("title"):
            self.fig.text(0.13 if not kwargs.get('nologo') else 0.02, 0.94, kwargs.get("title"), fontsize=18) 
        if kwargs.has_key("subtitle"):
            self.fig.text(0.13 if not kwargs.get('nologo') else 0.02, 0.91, kwargs.get("subtitle") )
        
        self.fig.text(0.01, 0.03, "%s :: generated %s" % (
                        kwargs.get('caption', 'Iowa Environmental Mesonet'),
                        mx.DateTime.now().strftime("%d %B %Y %I:%M %p %Z"),))

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
        for i, (lev, lbl) in enumerate(zip(clevs, clevlabels)):
            y = float(i) / (len(clevs) -1)
            fmt = '%s' if type(lbl) == type('a') else '%g'
            txt = cb2.ax.text(0.5, y, fmt % (lbl,), va='center', ha='center')
            txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                        foreground="w")])
            
        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def plot_values(self, lons, lats, vals, fmt='%s', valmask=None,
                    color='#000000', textsize=14, labels=None):
        """ Simply plot vals """        
        if valmask is None:
            valmask = [True] * len(lons)
        if labels is None:
            labels = [''] * len(lons)
        t = []
        for o,a,v,m, l in zip(lons, lats, vals, valmask, labels):
            if m:
                x,y = self.map(o, a)
                t0 = self.ax.text(x, y, fmt % (v,) , color=color,  
                                      size=textsize, zorder=Z_OVERLAY+2,
                                      va='bottom')
                t0.set_clip_on(True)
                t.append(t0)
                
                if l and l != '':
                    self.ax.text(x, y, l, color='k', 
                                      size=textsize - 4, zorder=Z_OVERLAY+1,
                                      va='top').set_clip_on(True)
                    
                
                
        white_glows = FilteredArtistList(t, GrowFilter(3))
        self.ax.add_artist(white_glows)
        white_glows.set_zorder(t[0].get_zorder()-0.1)

    def scatter(self, lons, lats, vals, clevs, **kwargs):
        """ Plot scatter points with some colorized symbology """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)

        colors = cmap( norm(vals) )
        x,y = self.map(lons, lats)
        self.ax.scatter(x, y, c=colors, edgecolors=colors)
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
            xbnds = self.ax.get_xlim()
            ybnds = self.ax.get_ylim()
            ll = self.map(xbnds[0], ybnds[0], inverse=True)
            ur = self.map(xbnds[1], ybnds[1], inverse=True)
            xi = np.linspace(ll[0], ur[0], 100)
            yi = np.linspace(ll[1], ur[1], 100)
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
            if not data.has_key( clidiv ):
                continue
            val = data.get( clidiv )
            c = cmap( norm([val,]) )[0]
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

    def fill_ugc_counties(self, data, bins=np.arange(0,101,10), **kwargs):
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
                c = cmap( norm([data[ugc],]) )[0]
            geom = loads( str(row[1]) )
            for polygon in geom:
                if polygon.exterior is None:
                    continue
                a = np.asarray(polygon.exterior)
                if ugc[:2] == 'AK':
                    if self.ak_ax is None:
                        continue
                    x,y = self.ak_map(a[:,0], a[:,1])
                    a = zip(x,y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    akpatches.append(p)
                    pass
                elif ugc[:2] == 'HI':
                    if self.hi_ax is None:
                        continue
                    x,y = self.hi_map(a[:,0], a[:,1])
                    a = zip(x,y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    hipatches.append(p)
                elif ugc[:2] == 'PR':
                    if self.pr_ax is None:
                        continue
                    x,y = self.pr_map(a[:,0], a[:,1])
                    a = zip(x,y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    prpatches.append(p)
                else:
                    x,y = self.map(a[:,0], a[:,1])
                    a = zip(x,y)
                    p = Polygon(a, fc=c, ec='None', zorder=2, lw=.1)
                    patches.append(p)

        if len(patches) > 0:
            self.ax.add_collection(
                        PatchCollection(patches,match_original=True))
        if len(akpatches) > 0 and self.ak_ax is not None:
            self.ak_ax.add_collection(
                        PatchCollection(akpatches,match_original=True))
        if len(hipatches) > 0 and self.hi_ax is not None:
            self.hi_ax.add_collection(
                        PatchCollection(hipatches,match_original=True))
        if len(prpatches) > 0 and self.pr_ax is not None:
            self.pr_ax.add_collection(
                        PatchCollection(prpatches,match_original=True))
        if kwargs.has_key('cmap'):
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
                  shapefile='/mesonet/data/gis/static/shape/4326/nws/cwas',
                  bins=np.arange(0,101,10),
                  lblformat='%.0f', cmap=maue(), **kwargs):
        """
        Added filled polygons to the plot based on key/value lookup pairs in
        the data dictionary
        """
        if data.has_key('JSJ'):
            data['SJU'] = data['JSJ']
        norm = mpcolors.BoundaryNorm(bins, cmap.N)
        
        self.map.readshapefile(shapefile, 'cwas', ax=self.ax)
        plotted = []
        for nshape, seg in enumerate(self.map.cwas):
            cwa = self.map.cwas_info[nshape]['CWA']
            thismap = self.map
            thisax = self.ax
            transform = False
            if not data.has_key( cwa ):
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
            val = data.get( cwa )
            c = cmap( norm([float(val),]) )[0]
            # Check area in meters... 100,000 x 100,000
            if self.map.cwas_info[nshape]['CWA'] not in plotted:
                mx, my = thismap(self.map.cwas_info[nshape]['LON'],
                                  self.map.cwas_info[nshape]['LAT'])
                txt = thisax.text(mx, my, lblformat % (labels.get(cwa, val),), zorder=100,
                         ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                         foreground="w")])
                plotted.append( cwa )
            if transform:
                seg = np.array( seg )
                # convert read shapefile back into lat / lon
                xx, yy = self.map( seg[:,0], seg[:,1] , inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)
                
            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)
        if kwargs.has_key('cmap'):
            del kwargs['cmap']
        self.draw_colorbar(bins, cmap, norm, **kwargs)

    def drawcwas(self):
        ''' Draw CWAS '''
        self.map.readshapefile('/mesonet/data/gis/static/shape/4326/nws/cwas', 'c')
        for nshape, seg in enumerate(self.map.c):
            poly=Polygon(seg, fill=False, ec='k', lw=.8, zorder=Z_POLITICAL)
            self.ax.add_patch(poly)

    def drawcounties(self):
        """ Draw counties """
        self.map.readshapefile('/mesonet/data/gis/static/shape/4326/iowa/iacounties', 'c')
        for nshape, seg in enumerate(self.map.c):
            poly=Polygon(seg, fill=False, ec='k', lw=.4, zorder=Z_POLITICAL)
            self.ax.add_patch(poly)

        
    def iemlogo(self):
        """ Draw a logo """
        logo = Image.open('/mesonet/www/apps/iemwebsite/htdocs/images/logo_small.png')
        ax3 = plt.axes([0.02,0.89,0.1,0.1], frameon=False, 
                       axisbg=(0.4471,0.6235,0.8117), yticks=[], xticks=[])
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
        
