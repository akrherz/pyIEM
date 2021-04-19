"""pyiem.plot.util Plotting Utilities!"""
# pylint: disable=import-outside-toplevel
import os

import numpy as np
import cartopy.crs as ccrs
import pandas as pd
from shapely.geometry import Polygon
import matplotlib.path as mpath
import matplotlib.patches as mpatches
import matplotlib.image as mpimage
import matplotlib.colors as mpcolors
from pyiem import reference
from pyiem.plot.colormaps import stretch_cmap

DATADIR = os.sep.join([os.path.dirname(__file__), "..", "data"])
LOGO_BOUNDS = (0.005, 0.91, 0.08, 0.086)
LOGOFILES = {"dep": "deplogo.png", "iem": "logo.png"}


def pretty_bins(minval, maxval, bins=8):
    """Return a **smooth** binning that encloses the min and max value.

    The returned array is +1 in size of the bins specified, since we want the
    bin edges.

    Args:
      minval (real): minimum value to enclose.
      maxval (real): maximum value to enclose.
      bins (int): number of bins to generate
    Returns:
      ``np.array`` of bins"""
    center = (maxval + minval) / 2.0
    return centered_bins(maxval - center, on=center, bins=bins)


def centered_bins(absmax, on=0, bins=8):
    """Return a **smooth** binning around some number.

    The returned array is +1 in size of the bins specified, since we want the
    bin edges.

    Args:
      absmax (real): positive distance from the `on` value for bins to enclose.
      on (real): where to center these bins.
      bins (int): number of bins to generate
    Returns:
      ``np.array`` of bins"""
    # We want an array returned with +1 bins
    sz = float(bins) / 2.0
    mx = (absmax) / sz
    interval = np.around(mx, 2)
    # We don't want any floating point numbers over 5
    if interval > 5 and interval * 100 % 100 != 0:
        interval = np.ceil(mx)
        return np.linspace(on - sz * interval, on + sz * interval, bins + 1)
    if mx == interval:
        return np.linspace(on - sz * interval, on + sz * interval, bins + 1)
    # Find a pretty interval >= mx
    c = [0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1, 1.5, 5]
    for interval in c:
        if interval > mx:
            break
    return np.linspace(on - sz * interval, on + sz * interval, bins + 1)


def draw_logo(fig, logoname):
    """Place the logo."""
    if logoname is None:
        return
    filename = LOGOFILES.get(logoname, "logo.png")
    fn = "%s/%s" % (DATADIR, filename)
    if not os.path.isfile(fn):
        return
    # Create a fake axes to place this Logo
    logo = mpimage.imread(fn)
    # imshow messes with the aspect, so about the best we can do here is
    # pin it to the upper edge
    ax = fig.add_axes(
        LOGO_BOUNDS, frameon=False, yticks=[], xticks=[], anchor="NW"
    )
    ax.imshow(logo, aspect="equal", zorder=-1)


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
    bbox = fig.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    return bbox.height * fig.dpi * ratio


def fitbox(fig, text, x0, x1, y0, y1, **kwargs):
    """Fit text into a NDC box.

    Args:
      textsize (int, optional): First attempt this textsize to see if it fits.
    """
    if text is None:
        return None
    figbox = fig.get_window_extent().transformed(
        fig.dpi_scale_trans.inverted()
    )
    # need some slop for decimal comparison below
    px0 = x0 * fig.dpi * figbox.width - 0.15
    px1 = x1 * fig.dpi * figbox.width + 0.15
    py0 = y0 * fig.dpi * figbox.height - 0.15
    py1 = y1 * fig.dpi * figbox.height + 0.15
    xanchor = x0
    if kwargs.get("ha", "") == "center":
        xanchor = x0 + (x1 - x0) / 2.0
    yanchor = y0
    if kwargs.get("va", "") == "center":
        yanchor = y0 + (y1 - y0) / 2.0
    txt = fig.text(
        xanchor,
        yanchor,
        text,
        fontsize=kwargs.get("textsize", 50),
        ha=kwargs.get("ha", "left"),
        va=kwargs.get("va", "bottom"),
        color=kwargs.get("color", "k"),
    )

    def _fits(txt):
        """Test for fitting."""
        tb = txt.get_window_extent(fig.canvas.get_renderer())
        return tb.x0 >= px0 and tb.x1 < px1 and tb.y0 >= py0 and tb.y1 <= py1

    if not _fits(txt):
        for size in range(50, 1, -2):
            txt.set_fontsize(size)
            if _fits(txt):
                break
    return txt


def make_axes(ndc_axbounds, extent, projection, aspect, is_geoextent=False):
    """Factory for making an axis

    Args:
      ndc_axbounds (list): the NDC coordinates of axes to create
      extent (list): x0,x1,y0,y1 *in projected space* plot extent, unless
        `is_geoextent` is based as True, then it is Geodetic.
      projection (ccrs.Projection): the projection of the axes
      aspect (str): matplotlib's aspect of axes
      is_geoextent(bool): is the passed extent Geodetic?

    Returns:
      ax
    """
    # Lazy import to prevent backend setting
    import matplotlib.pyplot as plt

    ax = plt.axes(
        ndc_axbounds,
        projection=projection,
        aspect=aspect,
        adjustable="datalim",
        facecolor=(0.4471, 0.6235, 0.8117),
    )
    # Get the frame at the proper zorder
    for _k, spine in ax.spines.items():
        spine.set_zorder(reference.Z_FRAME)
    ax.set_extent(extent, crs=None if is_geoextent else projection)
    # Sadly, we need to force a render so that the actual plot extent gets
    # calculated with the adjustable datalim above
    ax.figure.canvas.draw()
    return ax


def sector_setter(mp, axbounds, **kwargs):
    """use kwargs to set the MapPlot sector."""
    aspect = kwargs.get("aspect", "equal")

    if mp.sector == "cwa":
        mp.cwa = kwargs.get("cwa", "DMX")
        mp.ax = make_axes(
            axbounds,
            [
                reference.wfo_bounds[mp.cwa][0],
                reference.wfo_bounds[mp.cwa][2],
                reference.wfo_bounds[mp.cwa][1],
                reference.wfo_bounds[mp.cwa][3],
            ],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
        )
        mp.axes.append(mp.ax)
    elif mp.sector == "state":
        mp.state = kwargs.get("state", "IA")
        # We hard code aspect as Alaska does funny things with 'equal' set
        mp.ax = make_axes(
            axbounds,
            [
                reference.state_bounds[mp.state][0],
                reference.state_bounds[mp.state][2],
                reference.state_bounds[mp.state][1],
                reference.state_bounds[mp.state][3],
            ],
            reference.EPSG[3857],
            aspect if mp.state != "AK" else "auto",
            is_geoextent=True,
        )
        mp.axes.append(mp.ax)
    elif mp.sector in reference.SECTORS:
        mp.ax = make_axes(
            axbounds,
            reference.SECTORS[mp.sector],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
        )
        mp.axes.append(mp.ax)
    elif mp.sector == "iowawfo":
        mp.ax = make_axes(
            axbounds,
            [-99.6, -89.0, 39.8, 45.5],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
        )
        mp.axes.append(mp.ax)
    elif mp.sector == "custom":
        mp.ax = make_axes(
            axbounds,
            [kwargs["west"], kwargs["east"], kwargs["south"], kwargs["north"]],
            kwargs.get("projection", reference.LATLON),
            aspect,
            is_geoextent="projection" not in kwargs,
        )
        mp.axes.append(mp.ax)

    elif mp.sector == "north_america":
        mp.ax = make_axes(
            axbounds,
            [-4.5e6, 4.3e6, -3.9e6, 3.8e6],
            reference.EPSG[2163],
            "auto",
        )
        mp.axes.append(mp.ax)

    elif mp.sector in ["conus", "nws"]:
        mp.ax = make_axes(
            axbounds,
            [-2400000, 2300000, 27600, 3173000],
            reference.EPSG[5070],
            aspect,
        )
        mp.axes.append(mp.ax)

        if mp.sector == "nws":
            # Create PR
            mp.pr_ax = make_axes(
                [0.78, 0.055, 0.125, 0.1],
                [-68.0, -65.0, 17.5, 18.6],
                reference.LATLON,
                aspect,
                is_geoextent=True,
            )
            mp.axes.append(mp.pr_ax)
            # Create AK
            mp.ak_ax = make_axes(
                [0.015, 0.055, 0.28, 0.23],
                [-179.5, -129.0, 51.3, 71.5],
                reference.LATLON,
                "auto",
                is_geoextent=True,
            )
            mp.axes.append(mp.ak_ax)
            # Create HI via a glorious hack for now
            ln = mp.ax.plot(
                [-95.4, -85.24],
                [23.3, 27.7],
                transform=ccrs.PlateCarree(),
                color="None",
            )[0]
            bbox = ln.get_window_extent(mp.fig.canvas.get_renderer())
            width = mp.fig.canvas.get_width_height()[0]
            axwidth = (bbox.x1 - bbox.x0) / width
            mp.hi_ax = make_axes(
                [bbox.x0 / width, 0.055, axwidth, 0.14],
                [-161.0, -154.0, 18.5, 22.5],
                reference.LATLON,
                aspect,
                is_geoextent=True,
            )
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
    bound_verts = np.array(
        [
            (xlim[0], ylim[0]),
            (xlim[0], ylim[1]),
            (xlim[1], ylim[1]),
            (xlim[1], ylim[0]),
            (xlim[0], ylim[0]),
        ]
    )

    # A series of codes (1 and 2) to tell matplotlib whether to draw a lineor
    # move the "pen" (So that there's no connecting line)
    bound_codes = [mpath.Path.MOVETO] + (len(bound_verts) - 1) * [
        mpath.Path.LINETO
    ]
    poly_codes = [mpath.Path.MOVETO] + (len(poly_verts) - 1) * [
        mpath.Path.LINETO
    ]

    # Plot the masking patch
    path = mpath.Path(
        np.concatenate([bound_verts, poly_verts]), bound_codes + poly_codes
    )
    # remove data
    patch = mpatches.PathPatch(
        path, facecolor="white", edgecolor="none", zorder=reference.Z_CLIP
    )
    patch = ax.add_patch(patch)

    # Reset the plot limits to their original extents
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    return patch


def polygon_fill(mymap, geodf, data, **kwargs):
    """Generalized function for overlaying filled polygons on the map

    Args:
      mymap (MapPlot): The MapPlot instance
      geodf (GeoDataFrame): A GeoDataFrame with a `geom` column.
      data (dict): The dictionary of keys and values used for picking colors

    These are kwargs general to `polygon_fill`.
    **kwargs (Optional): Other things needed for mapping
    ilabel (Optional[bool]): should values be labelled? Defaults to `False`
    plotmissing (bool): should geometries not included in the `data`
        be mapped? Defaults to `True`
    color (str or dict): Providing an explicit color (used for both edge
        and fill).  Either provide one color or a dictionary to lookup a
        color by the mapping key.
    fc (str or dict): Same as `color`, but controls the fill color.
        Providing this value will over-ride any `color` setting.
    ec (str or dict): Same as `color`, but controls the edge color.
        Providing this value will over-ride any `color` setting.
    zorder (int): The zorder to use for this layer, default `Z_FILL`
    lw (float): polygon outline width
    """
    bins = kwargs.get("bins", np.arange(0, 101, 10))
    cmap = stretch_cmap(kwargs.get("cmap"), bins, extend=kwargs.get("extend"))
    ilabel = kwargs.get("ilabel", False)
    norm = mpcolors.BoundaryNorm(bins, cmap.N)
    lblformat = kwargs.get("lblformat", "%s")
    plotmissing = kwargs.get("plotmissing", True)
    color = kwargs.get("color")
    ec = kwargs.get("ec")
    fc = kwargs.get("fc")
    labels = kwargs.get("labels", {})
    zorder = kwargs.get("zorder", reference.Z_FILL)
    to_label = {"x": [], "y": [], "vals": []}
    # Merge data into the data frame
    geodf["val"] = pd.Series(data)
    if not plotmissing:
        geodf = geodf[~pd.isna(geodf["val"])].copy()
    for ax in mymap.axes:
        # Reproject data into plot native
        native = geodf["geom"].to_crs(ax.projection.proj4_init)
        # Filter data by bounds
        # pylint: disable=protected-access
        idx = native.intersects(ax._get_extent_geom())
        for polykey, row in geodf.loc[idx].iterrows():
            lbl = (
                labels.get(polykey, "-")
                if pd.isna(row["val"])
                else labels.get(polykey, lblformat % (row["val"],))
            )
            # How we compute a fill and edge color
            _fc, _ec = (None, None)
            if color is not None:
                if isinstance(color, str):
                    _fc, _ec = (color, color)
                else:
                    _fc = color.get(polykey, "white")
                    _ec = color.get(polykey, "k")
            if fc is not None:
                _fc = fc if isinstance(fc, str) else fc.get(polykey, "white")
            if ec is not None:
                _ec = ec if isinstance(ec, str) else ec.get(polykey, "k")
            _ec = "k" if _ec is None else _ec
            if _fc is None:
                _fc = (
                    "white"
                    if pd.isna(row["val"])
                    else cmap(norm([row["val"]]))[0]
                )
            for polyi, polygon in enumerate(native.loc[polykey]):
                if polygon.exterior is None:
                    continue
                a = np.asarray(polygon.exterior)
                p = mpatches.Polygon(
                    a[:, :2],
                    fc=_fc,
                    ec=_ec,
                    zorder=zorder,
                    lw=kwargs.get("lw", 0.1),
                )
                ax.add_patch(p)
                if ilabel and polyi == 0:
                    # prefer our stored centroid vs calculated one
                    mx = row.get("lon", polygon.centroid.x)
                    my = row.get("lat", polygon.centroid.y)
                    to_label["x"].append(mx)
                    to_label["y"].append(my)
                    to_label["vals"].append(lbl)
    if to_label:
        mymap.plot_values(
            to_label["x"],
            to_label["y"],
            to_label["vals"],
            labelbuffer=kwargs.get("labelbuffer", 1),
            textsize=12,
            textoutlinewidth=2,
            clip_on=True,
        )
    kwargs.pop("cmap", None)
    kwargs.pop("bins", None)
    if not kwargs.get("nocbar", False):
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
    verts = np.array(
        [
            (xlim[0], ylim[0]),
            (xlim[0], ylim[1]),
            (xlim[1], ylim[1]),
            (xlim[1], ylim[0]),
            (xlim[0], ylim[0]),
        ]
    )
    codes = [mpath.Path.MOVETO] + (len(verts) - 1) * [mpath.Path.LINETO]
    if isinstance(geom, Polygon):
        geom = [
            geom,
        ]
    for geo in geom:
        ccw = np.asarray(geo.exterior)[::-1]
        points = ax.projection.transform_points(
            ccrs.Geodetic(), ccw[:, 0], ccw[:, 1]
        )
        verts = np.concatenate([verts, points[:, :2]])
        codes = np.concatenate(
            [
                codes,
                [mpath.Path.MOVETO]
                + (points.shape[0] - 1) * [mpath.Path.LINETO],
            ]
        )

    path = mpath.Path(verts, codes)
    # Removes any external data
    patch = mpatches.PathPatch(
        path, facecolor="white", edgecolor="none", zorder=reference.Z_CLIP
    )
    ax.add_patch(patch)
    # Then gives a nice semitransparent look
    patch = mpatches.PathPatch(
        path,
        facecolor="black",
        edgecolor="none",
        zorder=reference.Z_CLIP2,
        alpha=0.65,
    )
    ax.add_patch(patch)
