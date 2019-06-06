"""pyiem.plot.util Plotting Utilities!"""

import numpy as np
import cartopy.crs as ccrs
import matplotlib.path as mpath
import matplotlib.patches as mpatches
import matplotlib.colors as mpcolors
import matplotlib.patheffects as PathEffects
from pyiem import reference
from pyiem.plot.colormaps import stretch_cmap


def fontscale(ratio, fig=None):
    """Return a font size suitable for this NDC ratio.

    Args:
      ratio (float): value between 0 and 1
      fig (matplotlib.Figure,optional): The Figure of interest

    Returns:
      float: font size
    """
    if fig is None:
        # Lazy import to prevent default backend setting
        import matplotlib.pyplot as plt
        fig = plt.gcf()
    bbox = fig.get_window_extent().transformed(
        fig.dpi_scale_trans.inverted()
    )
    return bbox.height * fig.dpi * ratio


def fitbox(fig, text, x0, x1, y0, y1, **kwargs):
    """Fit text into a NDC box."""
    figbox = fig.get_window_extent().transformed(
        fig.dpi_scale_trans.inverted())
    # need some slop for decimal comparison below
    px0 = x0 * fig.dpi * figbox.width - 0.15
    px1 = x1 * fig.dpi * figbox.width + 0.15
    py0 = y0 * fig.dpi * figbox.height - 0.15
    py1 = y1 * fig.dpi * figbox.height + 0.15
    # print("px0: %s px1: %s py0: %s py1: %s" % (px0, px1, py0, py1))
    xanchor = x0
    if kwargs.get('ha', '') == 'center':
        xanchor = x0 + (x1 - x0) / 2.
    yanchor = y0
    if kwargs.get('va', '') == 'center':
        yanchor = y0 + (y1 - y0) / 2.
    txt = fig.text(
        xanchor, yanchor, text,
        fontsize=50, ha=kwargs.get('ha', 'left'),
        va=kwargs.get('va', 'bottom'),
        color=kwargs.get('color', 'k')
    )
    for fs in range(50, 1, -2):
        txt.set_fontsize(fs)
        tbox = txt.get_window_extent(fig.canvas.get_renderer())
        # print("fs: %s tbox: %s" % (fs, str(tbox)))
        if (tbox.x0 >= px0 and tbox.x1 < px1 and tbox.y0 >= py0 and
                tbox.y1 <= py1):
            break
    return txt


def make_axes(ndc_axbounds, geoextent, projection, aspect):
    """Factory for making an axis

    Args:
      ndc_axbounds (list): the NDC coordinates of axes to create
      geoextent (list): x0,x1,y0,y1 the lon/lon extent of the axes to create
      projection (ccrs.Projection): the projection of the axes
      aspect (str): matplotlib's aspect of axes

    Returns:
      ax
    """
    # Lazy import to prevent backend setting
    import matplotlib.pyplot as plt
    ax = plt.axes(ndc_axbounds, projection=projection, aspect=aspect)
    ax.set_extent(geoextent)
    if aspect != 'equal':
        return ax
    # Render the canvas so we know what happened with our axis
    ax.figure.canvas.draw()
    # Compute the current NDC extent of the axes
    ndc_bbox = ax.get_position()
    # pixel_bbox = ax.get_window_extent()
    (projx0, projx1, projy0, projy1) = ax.get_extent()
    # print(ax.get_extent())
    # Figure out which axis got shrunk
    xscaled = ndc_bbox.width / float(ndc_axbounds[2])
    yscaled = ndc_bbox.height / float(ndc_axbounds[3])
    # compute the dx/dy of this image
    # dx = (projx1 - projx0) / pixel_bbox.width
    # dx = (projy1 - projy0) / pixel_bbox.height
    # expand one way or another to fit, via set_extent
    xneeded = (projx1 - projx0) / xscaled - (projx1 - projx0)
    yneeded = (projy1 - projy0) / yscaled - (projy1 - projy0)
    # print(("xscaled: %s xneeded: %.1f yscaled: %s yneeded: %.1f"
    #       ) % (xscaled, xneeded, yscaled, yneeded))
    newbounds = [projx0 - xneeded/2.,
                 projx1 + xneeded/2.,
                 projy0 - yneeded/2.,
                 projy1 + yneeded/2.]
    ax.set_extent(newbounds, crs=projection)
    # Render the canvas so we know what happened with our axis
    ax.figure.canvas.draw()
    return ax


def sector_setter(mp, axbounds, **kwargs):
    """use kwargs to set the MapPlot sector."""
    aspect = kwargs.get('aspect', 'equal')

    if mp.sector == 'cwa':
        mp.cwa = kwargs.get('cwa', 'DMX')
        mp.ax = make_axes(
            axbounds,
            [reference.wfo_bounds[mp.cwa][0],
             reference.wfo_bounds[mp.cwa][2],
             reference.wfo_bounds[mp.cwa][1],
             reference.wfo_bounds[mp.cwa][3]], ccrs.Mercator(), aspect)
        mp.axes.append(mp.ax)
    elif mp.sector == 'state':
        mp.state = kwargs.get('state', 'IA')
        # We hard code aspect as Alaska does funny things with 'equal' set
        mp.ax = make_axes(
            axbounds,
            [reference.state_bounds[mp.state][0],
             reference.state_bounds[mp.state][2],
             reference.state_bounds[mp.state][1],
             reference.state_bounds[mp.state][3]], ccrs.Mercator(),
            aspect if mp.state != 'AK' else 'auto')
        mp.axes.append(mp.ax)
    elif mp.sector in reference.SECTORS:
        mp.ax = make_axes(
            axbounds, reference.SECTORS[mp.sector], ccrs.Mercator(), aspect)
        mp.axes.append(mp.ax)
    elif mp.sector == 'iowawfo':
        mp.ax = make_axes(
            axbounds,
            [-99.6, -89.0, 39.8, 45.5], ccrs.Mercator(), aspect)
        mp.axes.append(mp.ax)
    elif mp.sector == 'custom':
        mp.ax = make_axes(
            axbounds,
            [kwargs['west'], kwargs['east'],
             kwargs['south'], kwargs['north']],
            kwargs.get('projection', ccrs.Mercator()), aspect)
        mp.axes.append(mp.ax)

    elif mp.sector == 'north_america':
        mp.ax = make_axes(
            axbounds,
            [-145.5, -2.566, 1, 46.352],
            ccrs.LambertConformal(
                central_longitude=-107.0, central_latitude=50.0),
            aspect)
        mp.axes.append(mp.ax)

    elif mp.sector in ['conus', 'nws']:
        mp.ax = make_axes(
            axbounds,
            [reference.CONUS_WEST + 14,
             reference.CONUS_EAST - 12,
             reference.CONUS_SOUTH,
             reference.CONUS_NORTH + 1], reference.EPSG[5070], aspect)
        mp.axes.append(mp.ax)

        if mp.sector == 'nws':
            # Create PR, AK, and HI sectors
            mp.pr_ax = make_axes(
                [0.78, 0.055, 0.125, 0.1],
                [-68.0, -65.0, 17.5, 18.6],
                ccrs.PlateCarree(central_longitude=-105.0),
                aspect)
            mp.axes.append(mp.pr_ax)
            # Create AK
            mp.ak_ax = make_axes(
                [0.015, 0.055, 0.25, 0.2],
                [-179.5, -129.0, 51.08, 72.1],
                ccrs.PlateCarree(central_longitude=-105.0),
                aspect)
            mp.axes.append(mp.ak_ax)
            # Create HI
            mp.hi_ax = make_axes(
                [0.47, 0.055, 0.2, 0.1],
                [-161.0, -154.0, 18.5, 22.5],
                ccrs.PlateCarree(central_longitude=-105.0),
                aspect)
            mp.axes.append(mp.hi_ax)


def mask_outside_polygon(poly_verts, ax=None):
    """
    We produce a polygon that lies between the plot border and some interior
    polygon.

    POLY_VERTS is in CCW order, as this is the interior of the polygon
    """
    if ax is None:
        # Lazy import to prevent default backend setting
        import matplotlib.pyplot as plt
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
    # remove data
    patch = mpatches.PathPatch(path, facecolor='white', edgecolor='none',
                               zorder=reference.Z_CLIP)
    patch = ax.add_patch(patch)

    # Reset the plot limits to their original extents
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    return patch


def polygon_fill(mymap, geo_provider, data, **kwargs):
    """Generalized function for overlaying filled polygons on the map

    Args:
      mymap (MapPlot): The MapPlot instance
      geo_provider (dict): The dictionary of keys and geometries
      data (dict): The dictionary of keys and values used for picking colors
      **kwargs (Optional): Other things needed for mapping
        ilabel (Optional[bool]): should values be labelled? Defaults to `False`
        plotmissing (bool): should geometries not included in the `data`
        be mapped? Defaults to `True`
    """
    bins = kwargs.get('bins', np.arange(0, 101, 10))
    cmap = stretch_cmap(kwargs.get('cmap'), bins)
    ilabel = kwargs.get('ilabel', False)
    norm = mpcolors.BoundaryNorm(bins, cmap.N)
    lblformat = kwargs.get('lblformat', '%s')
    labels = kwargs.get('labels', dict())
    plotmissing = kwargs.get('plotmissing', True)
    for polykey, polydict in geo_provider.items():
        # our dictionary is bytes so we need str
        val = data.get(polykey.decode('utf-8'), None)
        if val is None:
            if not plotmissing:
                continue
            lbl = labels.get(polykey.decode('utf-8'), '-')
            c = 'white'
        else:
            lbl = labels.get(polykey.decode('utf-8'), lblformat % (val, ))
            c = cmap(norm([val, ]))[0]
        # in python3, our dict types are byte arrays
        for polyi, polygon in enumerate(polydict.get(b'geom', [])):
            if polygon.exterior is None:
                continue
            a = np.asarray(polygon.exterior)
            for ax in mymap.axes:
                points = ax.projection.transform_points(ccrs.Geodetic(),
                                                        a[:, 0], a[:, 1])
                p = mpatches.Polygon(
                    points[:, :2], fc=c, ec='k', zorder=reference.Z_FILL,
                    lw=.1)
                ax.add_patch(p)
                if ilabel and polyi == 0:
                    txt = ax.text(polydict.get(b'lon', polygon.centroid.x),
                                  polydict.get(b'lat', polygon.centroid.y),
                                  lbl, zorder=100, clip_on=True,
                                  ha='center', va='center',
                                  transform=ccrs.PlateCarree())
                    txt.set_path_effects([
                        PathEffects.withStroke(linewidth=2, foreground="w")])

    kwargs.pop('cmap', None)
    kwargs.pop('bins', None)
    mymap.draw_colorbar(bins, cmap, norm, **kwargs)


def mask_outside_geom(ax, geom):
    """Create a white patch over the plot for what we want to ask out

    Args:
      ax (axes):
      geom (geometry):
    """
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    # Verticies of the plot boundaries in clockwise order
    verts = np.array([(xlim[0], ylim[0]), (xlim[0], ylim[1]),
                      (xlim[1], ylim[1]), (xlim[1], ylim[0]),
                      (xlim[0], ylim[0])])
    codes = [mpath.Path.MOVETO] + (len(verts) -
                                   1) * [mpath.Path.LINETO]
    for geo in geom:
        ccw = np.asarray(geo.exterior)[::-1]
        points = ax.projection.transform_points(ccrs.Geodetic(),
                                                ccw[:, 0], ccw[:, 1])
        verts = np.concatenate([verts, points[:, :2]])
        codes = np.concatenate([codes, [mpath.Path.MOVETO] +
                                (points.shape[0] - 1) * [mpath.Path.LINETO]])

    path = mpath.Path(verts, codes)
    # Removes any external data
    patch = mpatches.PathPatch(path, facecolor='white', edgecolor='none',
                               zorder=reference.Z_CLIP)
    ax.add_patch(patch)
    # Then gives a nice semitransparent look
    patch = mpatches.PathPatch(path, facecolor='black', edgecolor='none',
                               zorder=reference.Z_CLIP2, alpha=0.65)
    ax.add_patch(patch)
