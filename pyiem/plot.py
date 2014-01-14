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
from mpl_toolkits.basemap import Basemap, maskoceans
from matplotlib.colors import rgb2hex
from matplotlib.patches import Polygon
import matplotlib.cm as cm
import matplotlib.colors as mpcolors
import matplotlib.colorbar as mpcolorbar
import matplotlib.patheffects as PathEffects
import mx.DateTime
import numpy
from scipy.interpolate import griddata, Rbf
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


DATADIR = os.sep.join([os.path.dirname(__file__), 'data'])

from matplotlib.artist import Artist

def smooth1d(x, window_len):
    # copied from http://www.scipy.org/Cookbook/SignalSmooth

    s=numpy.r_[2*x[0]-x[window_len:1:-1],x,2*x[-1]-x[-1:-window_len:-1]]
    w = numpy.hanning(window_len)
    y=numpy.convolve(w/w.sum(),s,mode='same')
    return y[window_len-1:-window_len+1]

def smooth2d(A, sigma=3):

    window_len = max(int(sigma), 3)*2+1
    A1 = numpy.array([smooth1d(x, window_len) for x in numpy.asarray(A)])
    A2 = numpy.transpose(A1)
    A3 = numpy.array([smooth1d(x, window_len) for x in A2])
    A4 = numpy.transpose(A3)

    return A4

class BaseFilter(object):
    def prepare_image(self, src_image, dpi, pad):
        ny, nx, depth = src_image.shape
        #tgt_image = numpy.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
        padded_src = numpy.zeros([pad*2+ny, pad*2+nx, depth], dtype="d")
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
        new_im = numpy.empty([pad*2+ny, pad*2+nx, depth], dtype="d")
        alpha = new_im[:,:,3]
        alpha.fill(0)
        alpha[pad:-pad, pad:-pad] = im[:,:,-1]
        alpha2 = numpy.clip(smooth2d(alpha, self.pixels/72.*dpi) * 5, 0, 1)
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

def load_bounds2(filename):
    """
    Load the boundary file into a [numpy array]
    """
    res = numpy.loadtxt("%s/%s" % (DATADIR, filename), delimiter=',')
    return res

def load_bounds(filename):
    """
    Load the boundary file into a [numpy array]
    """
    res = numpy.loadtxt("%s/%s" % (DATADIR, filename))
    return numpy.column_stack(res)

def mask_outside_polygon(poly_verts, ax=None):
    """
    Plots a mask on the specified axis ("ax", defaults to plt.gca()) such
that
    all areas outside of the polygon specified by "poly_verts" are masked.

    "poly_verts" must be a list of tuples of the verticies in the polygon in
    counter-clockwise order.

    Returns the matplotlib.patches.PathPatch instance plotted on the figure.
    """
    import matplotlib.patches as mpatches
    import matplotlib.path as mpath

    if ax is None:
        ax = plt.gca()

    # Get current plot limits
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    # Verticies of the plot boundaries in clockwise order
    bound_verts = [(xlim[0], ylim[0]), (xlim[0], ylim[1]),
                   (xlim[1], ylim[1]), (xlim[1], ylim[0]),
                   (xlim[0], ylim[0])]

    # A series of codes (1 and 2) to tell matplotlib whether to draw a lineor
    # move the "pen" (So that there's no connecting line)
    bound_codes = [mpath.Path.MOVETO] + (len(bound_verts) - 1) *[mpath.Path.LINETO]
    poly_codes = [mpath.Path.MOVETO] + (len(poly_verts) - 1) *[mpath.Path.LINETO]

    # Plot the masking patch
    path = mpath.Path(bound_verts + poly_verts, bound_codes + poly_codes)
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
                self.pr_map.fillcontinents(color='0.7',zorder=0)
                self.ak_map.fillcontinents(color='0.7',zorder=0)
                self.hi_map.fillcontinents(color='0.7',zorder=0)

        self.map.fillcontinents(color='1.0', zorder=0) # Read docs on 0 meaning
        self.map.drawstates(linewidth=1.5, zorder=Z_OVERLAY, ax=self.ax)
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
        


        under = clevs[0]-(clevs[1]-clevs[0])
        over = clevs[-1]+(clevs[-1]-clevs[-2])
        blevels = numpy.concatenate([[under,], clevs, [over,]])
        cb2 = mpcolorbar.ColorbarBase(self.cax, cmap=cmap,
                                     norm=norm,
                                     boundaries=blevels,
                                     extend='both',
                                     ticks=None,
                                     spacing='uniform',
                                     orientation='vertical')
        for i, lev in enumerate(clevs):
            y = float(i) / (len(clevs) -1)
            txt = cb2.ax.text(0.5, y, '%g' % (lev,), va='center', ha='center')
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
                t.append(self.ax.text(x, y, fmt % (v,) , color=color,  
                                      size=textsize, zorder=Z_OVERLAY+2,
                                      va='bottom'))
                
                if l and l != '':
                    self.ax.text(x, y, l, color='k', 
                                      size=textsize - 4, zorder=Z_OVERLAY+1,
                                      va='top')
                    
                
                
        white_glows = FilteredArtistList(t, GrowFilter(3))
        self.ax.add_artist(white_glows)
        white_glows.set_zorder(t[0].get_zorder()-0.1)

    def hexbin(self, lons, lats, vals, clevs, **kwargs):
        """ hexbin wrapper """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        
        x, y = self.map(lons, lats)
        self.map.hexbin(x, y, C=vals, norm=norm,
                               cmap=cmap, zorder=Z_FILL)

        self.draw_colorbar(clevs, cmap, norm)

        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def pcolormesh(self, lons, lats, vals, clevs, **kwargs):
        """ pcolormesh wrapper """
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        
        self.map.pcolormesh(lons, lats, vals, norm=norm,
                               cmap=cmap, zorder=Z_FILL, latlon=True)

        if self.sector == 'iowa':
            ia_border = load_bounds("iowa_bnds.txt") # Only consider first
            xx,yy = self.map(ia_border[::-1,0], ia_border[::-1,1])            
            poly = zip(xx,yy)
            mask_outside_polygon(poly, ax=self.ax)

        self.draw_colorbar(clevs, cmap, norm)

        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')

    def contourf(self, lons, lats, vals, clevs, **kwargs):
        """ Contourf """
        if type(lons) == type([]):
            lons = numpy.array( lons )
            lats = numpy.array( lats )
            vals = numpy.array( vals )
        if vals.ndim == 1:
            # We need to grid!
            if self.sector == 'iowa':
                xi = numpy.linspace(reference.IA_WEST, reference.IA_EAST, 100)
                yi = numpy.linspace(reference.IA_SOUTH, reference.IA_NORTH, 100)
            elif self.sector == 'conus':
                xi = numpy.linspace(reference.CONUS_WEST, 
                                    reference.CONUS_EAST, 100)
                yi = numpy.linspace(reference.CONUS_SOUTH, 
                                    reference.CONUS_NORTH, 100)
            else:
                xi = numpy.linspace(reference.MW_WEST, reference.MW_EAST, 100)
                yi = numpy.linspace(reference.MW_SOUTH, reference.MW_NORTH, 100)
            xi, yi = numpy.meshgrid(xi, yi)
            #vals = griddata( zip(lons, lats), vals, (xi, yi) , 'cubic')
            #rbfi = Rbf(lons, lats, vals, function='cubic')
            nn = NearestNDInterpolator((lons, lats), vals)
            vals = nn(xi, yi)
            #vals = rbfi(xi, yi)
            lons = xi
            lats = yi
        if lons.ndim == 1:
            lons, lats = numpy.meshgrid(lons, lats)
        
        cmap = kwargs.get('cmap', maue())
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
                
        x, y = self.map(lons, lats)
        from scipy.signal import convolve2d
        window = numpy.ones((6, 6))
        vals = convolve2d(vals, window / window.sum(), mode='same', 
                          boundary='symm')
        #vals = maskoceans(lons, lats, vals, resolution='h')
        self.map.contourf(x, y, vals, clevs,
                          cmap=cmap, norm=norm, zorder=Z_FILL, extend='both')
        if self.sector == 'iowa':
            ia_border = load_bounds("iowa_bnds.txt") # Only consider first
            xx,yy = self.map(ia_border[::-1,0], ia_border[::-1,1])            
            poly = zip(xx,yy)
            mask_outside_polygon(poly, ax=self.ax)
        elif self.sector == 'conus':
            ia_border = load_bounds2("conus_bnds.txt") # Only consider first
            xx,yy = self.map(ia_border[::-1,0], ia_border[::-1,1])            
            poly = zip(xx,yy)
            mask_outside_polygon(poly, ax=self.ax)          
        elif self.sector == 'midwest':
            ia_border = load_bounds("midwest_bnds.txt") # Only consider first
            xx,yy = self.map(ia_border[::-1,0], ia_border[::-1,1])            
            poly = zip(xx,yy)
            mask_outside_polygon(poly, ax=self.ax)         
        self.draw_colorbar(clevs, cmap, norm)

        if kwargs.has_key('units'):
            self.fig.text(0.99, 0.03, "map units :: %s" % (kwargs['units'],),
                          ha='right')
            
    def fill_climdiv(self, data, 
                    shapefile='/mesonet/data/gis/static/shape/4326/nws/0.01/climdiv',
                  bins=numpy.arange(0,101,10),
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
                seg = numpy.array( seg )
                mx =  (numpy.max(seg[:,0]) + numpy.min(seg[:,0])) / 2.0
                my =  (numpy.max(seg[:,1]) + numpy.min(seg[:,1])) / 2.0
                txt = thisax.text(mx, my, lblformat % (val,), zorder=100,
                         ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                         foreground="w")])
                plotted.append( clidiv )
            if transform:
                seg = numpy.array( seg )
                xx, yy = self.map( seg[:,0], seg[:,1] , inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)
                
            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)

        self.draw_colorbar(bins, cmap, norm, **kwargs)

        

    def fill_states(self, data, 
                    shapefile='/mesonet/data/gis/static/shape/4326/nws/0.01/states',
                  bins=numpy.arange(0,101,10),
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
                seg = numpy.array( seg )
                xx, yy = self.map( seg[:,0], seg[:,1] , inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)
                
            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)

        self.draw_colorbar(bins, cmap, norm, **kwargs)

        

    def fill_cwas(self, data,
                  shapefile='/mesonet/data/gis/static/shape/4326/nws/cwas',
                  bins=numpy.arange(0,101,10),
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
                txt = thisax.text(mx, my, lblformat % (val,), zorder=100,
                         ha='center', va='center')
                txt.set_path_effects([PathEffects.withStroke(linewidth=2, 
                                                         foreground="w")])
                plotted.append( cwa )
            if transform:
                seg = numpy.array( seg )
                # convert read shapefile back into lat / lon
                xx, yy = self.map( seg[:,0], seg[:,1] , inverse=True)
                xx, yy = thismap(xx, yy)
                seg = zip(xx, yy)
                
            poly=Polygon(seg, fc=c, ec='k', lw=.4, zorder=Z_POLITICAL)
            thisax.add_patch(poly)

        self.draw_colorbar(bins, cmap, norm, **kwargs)



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
        ax.barh(numpy.arange(len(bins)), [1]*len(bins), height=1,
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
        
