"""pyiem.plot.util Plotting Utilities."""

# pylint: disable=import-outside-toplevel
import functools
import os
from pathlib import Path

import geopandas as gpd
import matplotlib.colors as mpcolors
import matplotlib.image as mpimage
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon

from pyiem import reference
from pyiem.plot.colormaps import stretch_cmap
from pyiem.reference import FIGSIZES, LATLON

from ._mpl import GeoPanel, SphericalMercatorPanel

DATADIR = os.sep.join([os.path.dirname(__file__), "..", "data"])
LOGO_BOUNDS = (0.005, 0.91, 0.08, 0.086)
LOGOFILES = {"dep": "deplogo.png", "iem": "logo.png", "nwa": "nwalogo.png"}


def update_kwargs_apctx(func):
    """Decorate things provided by an autoplot context dict."""

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        """Compute things and update things."""
        if "apctx" in kwargs:
            apctx = kwargs["apctx"]
            # If figsize is set, we take no other action
            if "figsize" not in kwargs:
                _r = apctx.get("_r", None)
                if _r in FIGSIZES:
                    kwargs["figsize"] = FIGSIZES[_r]
            # Merge in csector, this will override sector
            csector: str | None = apctx.get("csector", None)
            if csector is not None:
                # Quasi magic
                if len(csector) == 2:
                    kwargs["sector"] = "state"
                    kwargs["state"] = csector.upper()
                else:
                    kwargs["sector"] = csector
            # Merge in dpi, if not set
            dpi = apctx.get("dpi", None)
            if dpi is not None and "dpi" not in kwargs:
                kwargs["dpi"] = dpi
        return func(*args, **kwargs)

    return wrapped


def draw_features_from_shapefile(gp, name: str, **kwargs):
    """Add features as we need to."""
    name2 = name if name != "borders" else "admin_0_boundary_lines_land"
    boundpoly = gp.get_bounds_polygon()
    # Life choices: which resolution to use?
    threshold = 25 if gp.crs.is_geographic else 3e12
    resolution = "50m" if boundpoly.area > threshold else "10m"

    fastfn = (
        Path("/opt/miniconda3/pyiem_data/parquet")
        / str(gp.crs.to_epsg())
        / "natural_earth"
        / ("physical" if name != "borders" else "cultural")
        / f"ne_{resolution}_{name2}.parquet"
    )
    if fastfn.exists():
        df = gpd.read_parquet(fastfn).cx[
            slice(*gp.get_xlim()), slice(*gp.get_ylim())
        ]
    else:
        shpfn = (
            Path(
                os.environ.get(
                    "CARTOPY_OFFLINE_SHARED",
                    os.environ.get("CARTOPY_DATA_DIR"),
                )
            )
            / "shapefiles"
            / "natural_earth"
            / ("physical" if name != "borders" else "cultural")
            / f"ne_{resolution}_{name2}.shp"
        )
        df = (
            gpd.read_file(shpfn, engine="pyogrio")
            .to_crs(gp.crs)
            .cx[slice(*gp.get_xlim()), slice(*gp.get_ylim())]
        )
    if not df.empty:
        df.plot(ax=gp.ax, aspect=None, **kwargs)


def ramp2df(name) -> pd.DataFrame:
    """Load pyIEM color ramp into a Pandas DataFrame.

    Args:
      name (str): the name of the bundled color ramp.

    Returns
    -------
      pandas.DataFrame
    """
    return pd.read_csv(f"{DATADIR}/ramps/{name}.txt")


def pretty_bins(minval, maxval, bins=8):
    """Return a **smooth** binning that encloses the min and max value.

    The returned array is at most the specified bins + 1 in size, but could
    be smaller given this algorithm and the data range.

    Args:
      minval (real): minimum value to enclose.
      maxval (real): maximum value to enclose.
      bins (int): maximum number of bins to generate
    Returns:
    ``np.array`` of bins
    """
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
    ``np.array`` of bins
    """
    minval = on - absmax
    maxval = on + absmax
    vrange = maxval - minval
    step = vrange / float(bins)
    avail = [0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 25, 50]
    avail.extend([100, 150, 200, 250, 500, 750, 1000, 1e4, 1e5, 1e6])
    if step >= avail[-1]:
        raise ValueError(f"step: {step} too large to handle")
    # compute a new and round step value
    step = avail[np.digitize(step, avail)]
    # Create new min and max values
    minval = np.floor(minval / step) * step
    maxval = np.ceil(maxval / step) * step
    res = np.arange(minval, maxval + 0.001, step)
    # Account for some numerical instability
    if len(res) == bins + 1 and abs(res[bins // 2] - on) < 0.001:
        res[bins // 2] = on
    return res


def draw_logo(fig, logoname):
    """Place the logo."""
    if logoname is None:
        return
    filename = LOGOFILES.get(logoname, "logo.png")
    fn = os.path.join(DATADIR, filename)
    # Create a fake axes to place this Logo
    logo = mpimage.imread(fn)
    # imshow messes with the aspect, so about the best we can do here is
    # pin it to the upper edge
    ax = fig.add_axes(
        LOGO_BOUNDS, frameon=False, yticks=[], xticks=[], anchor="NW"
    )
    ax.imshow(logo, aspect="equal", zorder=-1)


def fontscale(ratio, fig):
    """Return a font size suitable for this NDC ratio.

    Args:
      ratio (float): value between 0 and 1
      fig (matplotlib.Figure,optional): The Figure of interest

    Returns
    -------
      float: font size
    """
    bbox = fig.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    # point size is 72 pts per inch
    return bbox.height * 72.0 * ratio


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
    fontsize = int(kwargs.get("textsize", kwargs.get("fontsize", 50)))
    txt = fig.text(
        xanchor,
        yanchor,
        text,
        fontsize=fontsize,
        ha=kwargs.get("ha", "left"),
        va=kwargs.get("va", "bottom"),
        color=kwargs.get("color", "k"),
        bbox=kwargs.get("bbox"),
    )

    def _fits(txt):
        """Test for fitting."""
        tb = txt.get_window_extent(fig.canvas.get_renderer())
        return tb.x0 >= px0 and tb.x1 < px1 and tb.y0 >= py0 and tb.y1 <= py1

    if not _fits(txt):
        for size in range(fontsize, 1, -2):
            txt.set_fontsize(size)
            if _fits(txt):
                break
    return txt


def make_panel(
    ndc_axbounds, fig, extent, crs, aspect, is_geoextent=False, **kwargs
) -> GeoPanel:
    """Make a GeoPanel.

    Args:
      ndc_axbounds (list): the NDC coordinates of axes to create
      extent (list): x0,x1,y0,y1 *in projected space* plot extent, unless
        `is_geoextent` is based as True, then it is Geodetic.
      crs (pyproj.CRS): the crs of the axes
      aspect (str): matplotlib's aspect of axes
      is_geoextent(bool): is the passed extent Geodetic?
      sector_label (bool): A Label that tracks what this is called
      background (str): background to use.

    Returns
    -------
        GeoPanel: the panel
    """
    # https://jdhao.github.io/2017/06/03/change-aspect-ratio-in-mpl/
    # aspect is data ratio divided by axes ratio
    sector_label = kwargs.get("sector_label", "")
    hacky = "spherical_mercator"
    cls = SphericalMercatorPanel if sector_label == hacky else GeoPanel
    gp = cls(
        fig,
        ndc_axbounds,
        crs,
        aspect=aspect,
        adjustable="datalim",
        facecolor=(0.4471, 0.6235, 0.8117),
        xticks=[],
        yticks=[],
        sector_label=sector_label,
    )
    # Get the frame at the proper zorder
    for spine in gp.ax.spines.values():
        spine.set_zorder(reference.Z_FRAME)
    # Turn off autoscale so that we can control the axis limits
    gp.ax.autoscale(False)
    # Set the extent
    gp.set_extent(extent, crs=None if is_geoextent else crs)
    gp.draw_background(kwargs.get("background"))
    return gp


def sector_setter(mp, axbounds, **kwargs):
    """Use kwargs to set the MapPlot sector."""
    aspect = kwargs.get("aspect", "auto")  # !important

    if mp.sector == "cwa":
        mp.cwa = kwargs.get("cwa", "DMX")
        gp = make_panel(
            axbounds,
            mp.fig,
            [
                reference.wfo_bounds[mp.cwa][0],
                reference.wfo_bounds[mp.cwa][2],
                reference.wfo_bounds[mp.cwa][1],
                reference.wfo_bounds[mp.cwa][3],
            ],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
            sector_label=f"cwa_{mp.cwa}",
            **kwargs,
        )
        mp.panels.append(gp)
    elif mp.sector == "fema_region":
        mp.fema_region = int(kwargs.get("fema_region", 7))
        gp = make_panel(
            axbounds,
            mp.fig,
            [
                reference.fema_region_bounds[mp.fema_region][0],
                reference.fema_region_bounds[mp.fema_region][2],
                reference.fema_region_bounds[mp.fema_region][1],
                reference.fema_region_bounds[mp.fema_region][3],
            ],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
            sector_label=f"fema_region_{mp.fema_region}",
            **kwargs,
        )
        mp.panels.append(gp)
    elif mp.sector == "state":
        mp.state = kwargs.get("state", "IA")
        gp = make_panel(
            axbounds,
            mp.fig,
            [
                reference.state_bounds[mp.state][0],
                reference.state_bounds[mp.state][2],
                reference.state_bounds[mp.state][1],
                reference.state_bounds[mp.state][3],
            ],
            reference.EPSG[3857 if mp.state != "AK" else 3467],
            aspect,
            is_geoextent=True,
            sector_label=f"state_{mp.state}",
            **kwargs,
        )
        mp.panels.append(gp)
    elif mp.sector == "iowawfo":
        gp = make_panel(
            axbounds,
            mp.fig,
            [-99.6, -89.0, 39.8, 45.5],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
            sector_label=mp.sector,
            **kwargs,
        )
        mp.panels.append(gp)
    elif mp.sector == "custom":
        # Crude check if we are crossing the anti-meridian
        if kwargs["west"] > 90 and kwargs["east"] < -90:
            # Convert to 0 to 360 longitude?
            kwargs["east"] += 360
        gp = make_panel(
            axbounds,
            mp.fig,
            [kwargs["west"], kwargs["east"], kwargs["south"], kwargs["north"]],
            kwargs.get("projection", reference.LATLON),
            aspect,
            is_geoextent="projection" not in kwargs,
            sector_label=mp.sector,
            **kwargs,
        )
        mp.panels.append(gp)
    elif mp.sector == "spherical_mercator":
        # Crude check if we are crossing the anti-meridian
        if kwargs["west"] > 90 and kwargs["east"] < -90:
            # Convert to 0 to 360 longitude?
            kwargs["east"] += 360
        gp = make_panel(
            axbounds,
            mp.fig,
            [kwargs["west"], kwargs["east"], kwargs["south"], kwargs["north"]],
            reference.EPSG[3857],
            "auto",
            is_geoextent="projection" not in kwargs,
            sector_label=mp.sector,
            background=kwargs.pop("background", "World_Street_Map"),
            **kwargs,
        )
        mp.panels.append(gp)
    elif mp.sector == "north_america":
        gp = make_panel(
            axbounds,
            mp.fig,
            [-4.5e6, 4.3e6, -3.9e6, 3.8e6],
            reference.EPSG[9311],
            "auto",
            sector_label=mp.sector,
            **kwargs,
        )
        mp.panels.append(gp)

    elif mp.sector in ["conus", "nws"]:
        gp = make_panel(
            axbounds,
            mp.fig,
            [-2400000, 2300000, 27600, 3173000],
            reference.EPSG[5070],
            aspect,
            sector_label=mp.sector,
            **kwargs,
        )
        mp.panels.append(gp)

        if mp.sector == "nws":
            width, height = mp.fig.canvas.get_width_height()
            # Create PR
            ln = mp.panels[0].plot(
                [-80.5, -74.55],
                [21.5, 22.8],
                color="None",
            )[0]
            bbox = ln.get_window_extent(mp.fig.canvas.get_renderer())
            mp.panels.append(
                make_panel(
                    [
                        bbox.x0 / width,
                        bbox.y0 / height,
                        (bbox.x1 - bbox.x0) / width,
                        (bbox.y1 - bbox.y0) / height,
                    ],
                    mp.fig,
                    [-68.0, -65.0, 17.5, 18.6],
                    reference.LATLON,
                    aspect,
                    is_geoextent=True,
                    sector_label="state_PR",
                    **kwargs,
                )
            )
            fitbox(
                mp.fig,
                "Puerto Rico",
                bbox.x0 / width,
                bbox.x1 / width,
                bbox.y1 / height,
                bbox.y1 / height + 0.1,
                color="white",
                bbox=dict(boxstyle="round,pad=0", color="k"),
            )
            # Create AK
            ln = mp.panels[0].plot(
                [-118.0, -105.5],
                [20.0, 30.25],
                color="None",
            )[0]
            bbox = ln.get_window_extent(mp.fig.canvas.get_renderer())
            mp.panels.append(
                make_panel(
                    [
                        bbox.x0 / width,
                        bbox.y0 / height,
                        (bbox.x1 - bbox.x0) / width,
                        (bbox.y1 - bbox.y0) / height,
                    ],
                    mp.fig,
                    [
                        reference.state_bounds["AK"][0],
                        reference.state_bounds["AK"][2],
                        reference.state_bounds["AK"][1],
                        reference.state_bounds["AK"][3],
                    ],
                    reference.EPSG[3467],
                    aspect,
                    is_geoextent=True,
                    sector_label="state_AK",
                    **kwargs,
                )
            )
            # Guam
            ln = mp.panels[0].plot(
                [-120.5, -117.5],
                [28.3, 31.7],
                color="None",
            )[0]
            bbox = ln.get_window_extent(mp.fig.canvas.get_renderer())
            mp.panels.append(
                make_panel(
                    [
                        bbox.x0 / width,
                        bbox.y0 / height,
                        (bbox.x1 - bbox.x0) / width,
                        (bbox.y1 - bbox.y0) / height,
                    ],
                    mp.fig,
                    [
                        reference.state_bounds["GU"][0],
                        reference.state_bounds["GU"][2],
                        reference.state_bounds["GU"][1],
                        reference.state_bounds["GU"][3],
                    ],
                    reference.LATLON,
                    aspect,
                    is_geoextent=True,
                    sector_label="state_GU",
                    **kwargs,
                )
            )
            fitbox(
                mp.fig,
                "Guam",
                bbox.x0 / width,
                bbox.x1 / width,
                bbox.y1 / height,
                bbox.y1 / height + 0.1,
                color="white",
                bbox=dict(boxstyle="round,pad=0", color="k"),
            )
            # Hawaii
            ln = mp.panels[0].plot(
                [-95.8, -85.24],
                [22.9, 27.7],
                color="None",
            )[0]
            bbox = ln.get_window_extent(mp.fig.canvas.get_renderer())
            mp.panels.append(
                make_panel(
                    [
                        bbox.x0 / width,
                        bbox.y0 / height,
                        (bbox.x1 - bbox.x0) / width,
                        (bbox.y1 - bbox.y0) / height,
                    ],
                    mp.fig,
                    [-161.0, -154.0, 18.5, 22.5],
                    reference.LATLON,
                    aspect,
                    is_geoextent=True,
                    sector_label="state_HI",
                    **kwargs,
                )
            )
    # Do last in case of name overlaps above
    elif mp.sector in reference.SECTORS:
        gp = make_panel(
            axbounds,
            mp.fig,
            reference.SECTORS[mp.sector],
            reference.EPSG[3857],
            aspect,
            is_geoextent=True,
            sector_label=mp.sector,
            **kwargs,
        )
        mp.panels.append(gp)
    # Kindof a hack for now
    if mp.panels:
        mp.ax = mp.panels[0].ax


def _mask_with_path(gp, path):
    """Make a path."""
    # Removes any external data
    patch = mpatches.PathPatch(
        path,
        facecolor="white",
        edgecolor="none",
        zorder=reference.Z_CLIP,
    )
    gp.ax.add_patch(patch)
    # Then gives a nice semitransparent look
    patch = mpatches.PathPatch(
        path,
        facecolor="black",
        edgecolor="none",
        zorder=reference.Z_CLIP2,
        alpha=0.65,
    )
    gp.ax.add_patch(patch)


def mask_outside_polygon(poly_verts, gp):
    """Make outside of a polygon.

    POLY_VERTS is in CCW order, as this is the interior of the polygon
    """
    # Get current plot limits
    xlim = gp.get_xlim()
    ylim = gp.get_ylim()

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
    _mask_with_path(gp, path)

    # Reset the plot limits to their original extents
    gp.ax.set_xlim(xlim)
    gp.ax.set_ylim(ylim)


def polygon_fill(mymap, geodf, data, **kwargs):
    """Generalize function for overlaying filled polygons on the map.

    Args:
      mymap (MapPlot): The MapPlot instance
      geodf (GeoDataFrame): A GeoDataFrame with a `geom` column.
      data (dict): The dictionary of keys and values used for picking colors

    Keyword Args:
      ilabel (Optional[bool]): should values be labelled? Defaults to `False`
      lblfmt (str,optional): format string for labels. Defaults to %s.
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
    # Sort the frame, placing the missing values at the beginning
    geodf = geodf.sort_values("val", na_position="first")
    if not plotmissing:
        geodf = geodf[pd.notna(geodf["val"])].copy()
    for gp in mymap.panels:
        # Reproject data into plot native, found out that clip() sometimes
        # returns a GeometryCollection, which geopandas hates to plot
        native = geodf.to_crs(gp.crs).cx[
            slice(*gp.get_xlim()), slice(*gp.get_ylim())
        ]
        if native.empty:
            continue
        native = native.copy()
        native["fc"] = pd.Series(fc) if fc else "white"
        native["ec"] = pd.Series(ec) if ec else "k"
        # Compute colors and such
        for idx, row in native.iterrows():
            lbl = (
                labels.get(idx, "-")
                if pd.isna(row["val"])
                else labels.get(idx, lblformat % (row["val"],))
            )
            # How we compute a fill and edge color
            _fc, _ec = (None, None)
            if color is not None:
                if isinstance(color, str):
                    _fc, _ec = (color, color)
                else:
                    _fc = color.get(idx, "white")
                    _ec = color.get(idx, "k")
            if fc is not None:
                _fc = fc if isinstance(fc, str) else fc.get(idx, "white")
            if ec is not None:
                _ec = ec if isinstance(ec, str) else ec.get(idx, "k")
            _ec = "k" if _ec is None else _ec
            if _fc is None:
                _fc = (
                    "white"
                    if pd.isna(row["val"])
                    else mpcolors.to_hex(cmap(norm([row["val"]]))[0])
                )
            native.at[idx, "fc"] = _fc
            native.at[idx, "ec"] = _ec
            if ilabel:
                # prefer our stored centroid vs calculated one
                mx = row.get("lon", native.at[idx, "geom"].centroid.x)
                my = row.get("lat", native.at[idx, "geom"].centroid.y)
                to_label["x"].append(mx)
                to_label["y"].append(my)
                to_label["vals"].append(lbl)

        native.plot(
            ax=gp.ax,
            fc=native["fc"].values,
            ec=native["ec"].values,
            aspect=None,
            zorder=zorder,
            lw=kwargs.get("lw", 0.1),
        )
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
    if kwargs.pop("draw_colorbar", True):
        mymap.draw_colorbar(bins, cmap, norm, **kwargs)


def mask_outside_geom(gp, geom):
    """Create a white patch over the plot for what we want to ask out.

    Args:
      gp (GeoPanel): The GeoPanel instance
      geom (geometry):
    """
    xlim = gp.get_xlim()
    ylim = gp.get_ylim()
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
        geom = MultiPolygon([geom])
    trans = Transformer.from_crs(LATLON, gp.crs, always_xy=True)
    for geo in geom.geoms:
        ccw = np.asarray(geo.exterior.coords)
        if not geo.exterior.is_ccw:
            ccw = ccw[::-1]
        points = trans.transform(ccw[:, 0], ccw[:, 1])
        # pylint: disable=unsubscriptable-object
        ar = np.column_stack([*points])[:-1]
        verts = np.concatenate([verts, ar])
        codes = np.concatenate(
            [
                codes,
                [mpath.Path.MOVETO] + (ar.shape[0] - 1) * [mpath.Path.LINETO],
            ]
        )

    path = mpath.Path(verts, codes)
    _mask_with_path(gp, path)
    # Reset the plot limits to their original extents
    gp.ax.set_xlim(xlim)
    gp.ax.set_ylim(ylim)
