"""Helpers for IEM's ERA5-Land processing.

This is heavily weighted to what IEMRE is doing.
"""

from typing import Optional

import numpy as np
from affine import Affine

from pyiem import iemre

DX = 0.1
DY = 0.1


def _roundup(val: float) -> float:
    """Round up to the nearest 0.1"""
    return np.ceil(val / 0.1) * 0.1


def _rounddown(val: float) -> float:
    """Round down to the nearest 0.1"""
    return np.floor(val / 0.1) * 0.1


DOMAINS = {"conus": {}, "china": {}, "europe": {}, "sa": {}}

for _dom, meta in DOMAINS.items():
    meta["WEST"] = _roundup(iemre.DOMAINS[_dom]["west_edge"])
    meta["EAST"] = _rounddown(iemre.DOMAINS[_dom]["east_edge"])
    meta["SOUTH"] = _roundup(iemre.DOMAINS[_dom]["south_edge"])
    meta["NORTH"] = _rounddown(iemre.DOMAINS[_dom]["north_edge"])

    meta["XAXIS"] = np.arange(meta["WEST"], meta["EAST"] + 0.01, DX)
    meta["YAXIS"] = np.arange(meta["SOUTH"], meta["NORTH"] + 0.01, DY)

    meta["WEST_EDGE"] = meta["XAXIS"][0] - DX / 2.0
    meta["EAST_EDGE"] = meta["XAXIS"][-1] + DX / 2.0
    meta["SOUTH_EDGE"] = meta["YAXIS"][0] - DY / 2.0
    meta["NORTH_EDGE"] = meta["YAXIS"][-1] + DY / 2.0
    # netcdf storage is bottom up
    meta["AFFINE_NC"] = Affine(
        DX,
        0.0,
        meta["WEST_EDGE"],
        0.0,
        DY,
        meta["SOUTH_EDGE"],
    )
    meta["NX"] = len(meta["XAXIS"])
    meta["NY"] = len(meta["YAXIS"])


def find_ij(
    lon: float, lat: float, domain: str = "conus"
) -> tuple[Optional[int], Optional[int]]:
    """Find the grid cell for the provided lon/lat"""
    _meta = DOMAINS[domain]
    if (
        lon < _meta["WEST_EDGE"]
        or lon > _meta["EAST_EDGE"]
        or lat < _meta["SOUTH_EDGE"]
        or lat > _meta["NORTH_EDGE"]
    ):
        return None, None
    i = int((lon - _meta["WEST_EDGE"]) / DX)
    j = int((lat - _meta["SOUTH_EDGE"]) / DY)
    return i, j
