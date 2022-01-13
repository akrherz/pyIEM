"""Utility class to help with fast zonal_stats work"""
from collections import namedtuple

import numpy as np
from rasterstats import zonal_stats
from pyiem.util import LOG

GRIDINFO = namedtuple("GridInfo", ["x0", "y0", "xsz", "ysz", "mask"])


class CachingZonalStats:
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
            LOG.warning(
                "Cowardly refusing to compute gridnav with None geometries"
            )
            return
        # TODO: check nodata usage here
        zs = zonal_stats(
            geometries,
            grid,
            affine=self.affine,
            nodata=-1,
            all_touched=True,
            raster_out=True,
        )
        (gridysz, gridxsz) = grid.shape
        LOG.debug("in grid size y: %s x: %s", gridysz, gridxsz)
        for entry in zs:
            aff = entry["mini_raster_affine"]
            LOG.debug(aff)
            x0 = int((aff.c - self.affine.c) / self.affine.a)
            y0 = int((self.affine.f - aff.f) / abs(self.affine.e))
            (ysz, xsz) = entry["mini_raster_array"].mask.shape
            mask = entry["mini_raster_array"].mask
            LOG.debug("IN: x0: %s y0: %s xsz: %s ysz: %s", x0, y0, xsz, ysz)
            if x0 >= gridxsz or y0 >= gridysz:
                LOG.debug("out of bounds, skipping")
                self.gridnav.append(None)
                continue
            if x0 < 0:
                mask = mask[:, abs(x0) :]
                xsz -= abs(x0)
                x0 = 0
            if (x0 + xsz) >= gridxsz:
                clipx = (x0 + xsz) - gridxsz
                LOG.debug("clipping %s x points", clipx)
                mask = mask[:, : (0 - clipx)]
                xsz -= clipx
            if y0 < 0:
                mask = mask[abs(y0) :, :]
                ysz -= abs(y0)
                y0 = 0
            if (y0 + ysz) >= gridysz:
                clipy = (y0 + ysz) - gridysz
                LOG.debug("clipping %s y points", clipy)
                mask = mask[: (0 - clipy), :]
                ysz -= clipy

            # TODO: likely need some more thought above to prevent this
            if ysz < 0 or xsz < 0:
                self.gridnav.append(None)
                continue

            LOG.debug("OUT: x0: %s y0: %s xsz: %s ysz: %s", x0, y0, xsz, ysz)
            self.gridnav.append(
                GRIDINFO(x0=x0, y0=y0, xsz=xsz, ysz=ysz, mask=mask)
            )

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
            if nav is None:
                res.append(None)
                continue
            res.append(
                stat(
                    np.ma.array(
                        grid[
                            nav.y0 : (nav.y0 + nav.ysz),
                            nav.x0 : (nav.x0 + nav.xsz),
                        ],
                        mask=nav.mask,
                    )
                )
            )
        return res
