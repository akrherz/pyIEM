"""Utility class to help with fast zonal_stats work"""
from __future__ import print_function
from collections import namedtuple
import logging

import numpy as np
from rasterstats import zonal_stats

_LOG = logging.getLogger(__name__)
GRIDINFO = namedtuple("GridInfo", ['x0', 'y0', 'xsz', 'ysz', 'mask'])


class CachingZonalStats(object):
    """Implements a cache to speed up zonal_stats computation"""

    def __init__(self, affine):
        """constructor

        Note: This library assumes that *you* enforce grid(0,0) is upper-left,
          this means that you should have a negative dy in the affine and use
          `np.flipud` for grids that have (0,0) in lower-left

        Args:
          affine (Affine): The base affine used to define the grid
        """
        self.affine = affine
        self.gridnav = []

    def compute_gridnav(self, geometries, grid):
        """Figure out how these geometries map to our grid

        Args:
          grid (numpy.ndarray): the array to sample values for
          geometries (geopandas.GeoSeries): geometries to compute over, this
            should not change over the lifetime of this object
        """
        if geometries is None:
            _LOG.warn(("Cowardly refusing to compute gridnav "
                       "with None geometries"))
            return
        # TODO: check nodata usage here
        zs = zonal_stats(geometries, grid, affine=self.affine, nodata=-1,
                         all_touched=True, raster_out=True)
        for entry in zs:
            aff = entry['mini_raster_affine']
            x0 = int((aff.c - self.affine.c) / self.affine.a)
            y0 = int(abs((self.affine.f - aff.f) / self.affine.e))
            (ysz, xsz) = entry['mini_raster_array'].mask.shape
            self.gridnav.append(
                GRIDINFO(x0=x0, y0=y0,
                         xsz=xsz, ysz=ysz,
                         mask=entry['mini_raster_array'].mask))

    def gen_stats(self, grid, geometries=None, stat=np.ma.mean):
        """Compute the zonal_stats for the provided geometries and grid

        Note: the passed `grid` should have (0,0) in upper-left, np.flipud()

        Args:
          grid (numpy.ndarray): the array to sample values for
          geometries (geopandas.GeoSeries): geometries to compute over, this
            should not change over the lifetime of this object
          stat (function): the function to compute over the masked grid

        Returns:
          tuple(dict): the ordered results of our work
        """
        if not self.gridnav:
            self.compute_gridnav(geometries, grid)
        res = []
        for nav in self.gridnav:
            res.append(stat(np.ma.array(
                grid[nav.y0:(nav.y0 + nav.ysz),
                     nav.x0:(nav.x0 + nav.xsz)], mask=nav.mask)))
        return res
