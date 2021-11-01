"""A custom axes implementation."""
# pylint: disable=unsubscriptable-object,unpacking-non-sequence

# Third party libraries
from shapely.geometry import Polygon
import geopandas as gpd
from pyproj import Transformer

# Local imports
from pyiem.reference import LATLON


class GeoPanel:
    """
    A container class holding references to a matplotlib axes.
    """

    def __init__(self, fig, rect, crs, **kwargs):
        """
        Initialize the axes.
        """
        self.figure = fig
        self.ax = self.figure.add_axes(rect, **kwargs)
        self.crs = crs

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
