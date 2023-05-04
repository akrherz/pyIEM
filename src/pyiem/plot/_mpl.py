"""A custom axes implementation."""
# pylint: disable=unsubscriptable-object,unpacking-non-sequence
import math
import os
from io import BytesIO

import geopandas as gpd

# Third party libraries
import numpy as np
import rasterio
import requests
from PIL import Image
from pymemcache.client import Client
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from shapely.geometry import Polygon

# Local imports
from pyiem.reference import EPSG, LATLON, Z_FILL
from pyiem.util import LOG, load_geodf

# Zoom 0 through 24
METERS_PER_PIXEL = [
    float(x)
    for x in (
        "156543 78271.5 39135.8 19567.88 9783.94 4891.97 2445.98 1222.99 "
        "611.5 305.75 152.87 76.44 38.219 19.109 9.555 4.777 2.3887 1.1943 "
        "0.5972 0.2986 0.14929 0.074646 0.037323 0.0186615 0.00933075"
    ).split()
]


def get_tile_lat_lng(zoom, x, y):
    """convert Google-style Mercator tile coordinate to
    (lat, lng) of top-left corner of tile"""

    # "map-centric" latitude, in radians:
    lat_rad = math.pi - 2 * math.pi * y / (2**zoom)
    # true latitude:
    lat_rad = 2 * math.atan(math.exp(lat_rad)) - math.pi / 2
    lat = lat_rad * 180.0 / math.pi

    # longitude maps linearly to map, so we simply scale:
    lng = -180.0 + 360.0 * x / (2**zoom)

    return (lat, lng)


def get_lat_lng_tile(lat, lng, zoom):
    """convert lat/lng to Google-style Mercator tile coordinate (x, y)
    at the given zoom level"""

    lat_rad = lat * math.pi / 180.0
    # "map-centric" latitude, in radians:
    lat_rad = math.log(math.tan((lat_rad + math.pi / 2) / 2))

    x = 2**zoom * (lng + 180.0) / 360.0
    y = 2**zoom * (math.pi - lat_rad) / (2 * math.pi)

    return (x, y)


def get_tile_data(url):
    """Fetch the tile and hope memcached has it."""
    key = url.split("//")[1]
    mc = Client("iem-memcached:11211", timeout=5)
    res = mc.get(key)
    if res is None:
        LOG.info("Fetching %s", url)
        req = requests.get(url, timeout=10)
        res = req.content
        mc.set(key, res)
    mc.close()
    bio = BytesIO(res)
    bio.seek(0)
    with Image.open(bio) as pilimg:
        im = np.asarray(pilimg)
    return im


def draw_wmts(panel, background):
    """todo"""
    xmin, xmax, ymin, ymax = panel.get_extent(crs=EPSG[4326])
    tx0, ty0 = get_lat_lng_tile(ymax, xmin, panel.zoom)
    tx1, ty1 = get_lat_lng_tile(ymin, xmax, panel.zoom)
    transform = Transformer.from_crs(EPSG[4326], EPSG[3857], always_xy=True)
    for y in range(int(ty0), int(ty1) + 1):
        for x in range(int(tx0), int(tx1) + 1):
            minlat, minlon = get_tile_lat_lng(panel.zoom, x, y + 1)
            maxlat, maxlon = get_tile_lat_lng(panel.zoom, x + 1, y)

            x0, y0 = transform.transform(minlon, maxlat)
            x1, y1 = transform.transform(maxlon, minlat)
            try:
                im = get_tile_data(
                    "https://services.arcgisonline.com/arcgis/rest/services/"
                    f"{background}/MapServer/tile/{panel.zoom}/{y}/{x}"
                )
            except Exception as exp:
                LOG.info(exp)
                continue

            panel.ax.imshow(
                im / 255.0,
                interpolation="nearest",  # prevents artifacts
                extent=(x0, x1, y0, y1),
                origin="lower",
                zorder=Z_FILL,
            ).set_rasterized(True)

    panel.ax.annotate(
        "Basemap Courtesy ESRI",
        xy=(1, 0),
        bbox=dict(color="white"),
        ha="right",
        va="bottom",
        zorder=1000,
        xycoords="axes fraction",
    )

    # Don't ask
    (
        load_geodf("SLC")
        .to_crs(panel.crs)
        .plot(
            ax=panel.ax,
            aspect=None,
            color="#f4f2db",
            zorder=Z_FILL,
        )
    )


def draw_background(panel, background):
    """Draw the background for this plot!"""
    if background is None:
        return
    datadirs = [
        os.sep.join(
            [
                os.path.dirname(__file__),
                "..",
                "data",
                "backgrounds",
                background,
            ]
        ),
        f"/opt/miniconda3/pyiem_data/backgrounds/{background}",
    ]
    src_epsg = str(panel.crs)
    rasterfn = f"{panel.get_sector_label()}_{src_epsg.split(':')[1]}.png"
    full = os.sep.join([datadirs[0], rasterfn])
    if not os.path.isfile(full):
        full = os.sep.join([datadirs[1], rasterfn])
        if not os.path.isfile(full):
            rasterfn = "default_4326.png"
            full = os.sep.join([datadirs[0], rasterfn])
            src_epsg = "EPSG:4326"
    worldfn = f"{full[:-4]}.wld"
    with open(worldfn, encoding="ascii") as fh:
        (dx, _, _, dy, west, north) = [float(x) for x in fh]
    src_aff = rasterio.Affine(dx, 0, west, 0, dy, north)
    src_crs = {"init": src_epsg}
    (px0, px1, py0, py1) = panel.get_extent()
    pbbox = panel.ax.get_window_extent()
    pdx = (px1 - px0) / pbbox.width
    pdy = (py1 - py0) / pbbox.height
    dest_aff = rasterio.Affine(pdx, 0, px0, 0, pdy, py0)
    res = np.zeros((int(pbbox.height), int(pbbox.width), 3), dtype=np.uint8)
    band = np.zeros((int(pbbox.height), int(pbbox.width)), dtype=np.uint8)
    with rasterio.open(full) as src:
        data = src.read()
        for i in range(3):
            reproject(
                data[i, :, :],
                band,
                src_transform=src_aff,
                src_crs=src_crs,
                src_nodata=0,
                dst_transform=dest_aff,
                dst_crs={"init": str(panel.crs)},
                resampling=Resampling.nearest,
            )
            res[:, :, i] = band
    panel.ax.imshow(
        res / 255.0,
        interpolation="nearest",  # prevents artifacts
        extent=(px0, px1, py0, py1),
        origin="lower",
        zorder=-1,
    ).set_rasterized(True)


class GeoPanel:
    """
    A container class holding references to a matplotlib axes.
    """

    def __init__(self, fig, rect, crs, **kwargs):
        """
        Initialize the axes.
        """
        self.sector_label = kwargs.pop("sector_label", "")
        self.figure = fig
        self.ax = self.figure.add_axes(rect, **kwargs)
        self.crs = crs
        self.zoom = None

    draw_background = draw_background

    def get_sector_label(self) -> str:
        """Return the property"""
        return self.sector_label

    def get_bounds_polygon(self):
        """Return the axes extent as a shapely polygon bounds."""
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        return Polygon(
            [
                (xlim[0], ylim[0]),
                (xlim[0], ylim[1]),
                (xlim[1], ylim[1]),
                (xlim[1], ylim[0]),
            ]
        )

    def get_extent(self, crs=None):
        """Return the axes extent in axes CRS or given CRS.

        Returns:
            (xmin, xmax, ymin, ymax)
        """
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        if crs:
            transform = Transformer.from_crs(self.crs, crs, always_xy=True)
            xlim, ylim = transform.transform(xlim, ylim)
        return xlim + ylim

    def set_extent(self, extent, crs=None):
        """
        Set the extent of the axes.

        Args:
            extent: (xmin, xmax, ymin, ymax)
            crs: (optional) the CRS of the extent. default is 4326.
        """
        transform = Transformer.from_crs(
            LATLON if crs is None else crs,
            self.crs,
            always_xy=True,
        )
        ll = transform.transform(extent[0], extent[2])
        lr = transform.transform(extent[1], extent[2])
        ur = transform.transform(extent[1], extent[3])
        ul = transform.transform(extent[0], extent[3])
        xmin = min(ll[0], ul[0])
        xmax = max(lr[0], ur[0])
        ymin = min(ll[1], lr[1])
        ymax = max(ul[1], ur[1])
        if self.ax.get_aspect() == "auto":
            # Holy cow, we are in control to attempt to implement equal
            bbox = self.ax.get_window_extent().transformed(
                self.figure.dpi_scale_trans.inverted(),
            )
            display_ratio = bbox.height / bbox.width
            dx = xmax - xmin
            dy = ymax - ymin
            data_ratio = dy / dx
            if display_ratio > data_ratio:
                # We need to expand the data in y
                yadd = dx * display_ratio - dy
                ymin -= yadd / 2
                ymax += yadd / 2
            else:
                # We need to expand the data in x
                xadd = dy / display_ratio - dx
                xmin -= xadd / 2
                xmax += xadd / 2
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)

    def get_xlim(self):
        """Proxy"""
        return self.ax.get_xlim()

    def get_ylim(self):
        """Proxy"""
        return self.ax.get_ylim()

    def add_geometries(self, features, crs, *args, **kwargs):
        """
        Add a feature to the axes.
        """
        df = gpd.GeoDataFrame({"geometry": features}, crs=crs).to_crs(self.crs)
        df.plot(ax=self.ax, aspect=None, *args, **kwargs)

    def plot(self, x, y, **kwargs):
        """Proxy"""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.plot(x, y, **kwargs)

    def transform_lonlat(self, x, y):
        """Convert back."""
        transform = Transformer.from_crs(LATLON, self.crs, always_xy=True)
        return transform.transform(x, y)

    def text(self, x, y, s, **kwargs):
        """Proxy"""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.text(x, y, s, **kwargs)

    def scatter(self, x, y, **kwargs):
        """Proxy"""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.scatter(x, y, **kwargs)

    def hexbin(self, x, y, vals, **kwargs):
        """Proxy to hexbin that handles reprojection."""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.hexbin(x, y, C=vals, **kwargs)

    def contourf(self, x, y, vals, clevs, **kwargs):
        """Proxy to contourf that handles reprojection."""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.contourf(x, y, vals, clevs, **kwargs)

    def contour(self, x, y, vals, clevs, **kwargs):
        """Proxy to contour that handles reprojection."""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.contour(x, y, vals, clevs, **kwargs)

    def pcolormesh(self, x, y, vals, **kwargs):
        """Proxy to pcolormesh."""
        crs = kwargs.pop("crs", LATLON)
        transform = Transformer.from_crs(crs, self.crs, always_xy=True)
        x, y = transform.transform(x, y)
        return self.ax.pcolormesh(x, y, vals, **kwargs)


class SphericalMercatorPanel(GeoPanel):
    """Specialized panel that maintains aspect."""

    def draw_background(self, background):
        """call"""
        if background is None:
            return
        draw_wmts(self, background)

    def set_extent(self, extent, crs=None):
        """
        Set the extent of the axes.

        Args:
            extent: (xmin, xmax, ymin, ymax)
            crs: (optional) the CRS of the extent. default is 4326.
        """
        transform = Transformer.from_crs(
            LATLON if crs is None else crs,
            self.crs,
            always_xy=True,
        )
        # Get the bounds in our local coordinates
        ll = transform.transform(extent[0], extent[2])
        lr = transform.transform(extent[1], extent[2])
        ur = transform.transform(extent[1], extent[3])
        ul = transform.transform(extent[0], extent[3])
        xmin = min(ll[0], ul[0])
        xmax = max(lr[0], ur[0])
        ymin = min(ll[1], lr[1])
        ymax = max(ul[1], ur[1])
        # rectify to square pixels
        bbox = self.ax.get_window_extent().transformed(
            self.figure.dpi_scale_trans.inverted(),
        )
        display_ratio = bbox.height / bbox.width
        dx = xmax - xmin
        dy = ymax - ymin
        data_ratio = dy / dx
        if display_ratio > data_ratio:
            # We need to expand the data in y
            yadd = dx * display_ratio - dy
            ymin -= yadd / 2
            ymax += yadd / 2
        else:
            # We need to expand the data in x
            xadd = dy / display_ratio - dx
            xmin -= xadd / 2
            xmax += xadd / 2

        # Now we muck to get an int zoom level
        dx = (xmax - xmin) / (bbox.width * 100.0)
        self.zoom = np.digitize(dx, METERS_PER_PIXEL) - 1

        # Now we recompute the bounds
        centerx = (xmax + xmin) / 2.0
        centery = (ymax + ymin) / 2.0
        xmin = centerx - METERS_PER_PIXEL[self.zoom] * (bbox.width * 50.0)
        xmax = centerx + METERS_PER_PIXEL[self.zoom] * (bbox.width * 50.0)
        ymin = centery - METERS_PER_PIXEL[self.zoom] * (bbox.height * 50.0)
        ymax = centery + METERS_PER_PIXEL[self.zoom] * (bbox.height * 50.0)

        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
