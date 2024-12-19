"""Helper for PRISM BIL data"""

import datetime

import numpy as np
from affine import Affine

NX = 1405
NY = 621

# This is the center of the upper left pixel
NORTH = 49.91666666667
WEST = -125.0

# This is the center of the lower right pixel
SOUTH = 24.08333333333
EAST = -66.50
DX = 1 / 24.0
DY = 1 / 24.0

# For the netcdf storage, we care about the lower left corner edge
SOUTH_EDGE = SOUTH - DY / 2.0
WEST_EDGE = WEST - DX / 2.0
EAST_EDGE = EAST + DX / 2.0
NORTH_EDGE = NORTH + DY / 2.0

# Definition of left and bottom edges of grid cells
XAXIS = WEST_EDGE + np.arange(NX) * DX
YAXIS = SOUTH_EDGE + np.arange(NY) * DY

# This is the affine from the PRISM BIL file
AFFINE_NATIVE = Affine(DX, 0.0, WEST_EDGE, 0.0, -DY, NORTH_EDGE)
# This is the affine for the netcdf file
AFFINE_NC = Affine(DX, 0.0, WEST_EDGE, 0.0, DY, SOUTH_EDGE)


def daily_offset(ts):
    """Compute the timestamp index in the netcdf file"""
    # In case ts is passed here as a datetime.date object
    ts = datetime.datetime(ts.year, ts.month, ts.day)
    return int((ts - ts.replace(month=1, day=1)).days)


def find_ij(lon, lat):
    """Compute which grid cell this lon, lat resides within"""
    if (
        lon < WEST_EDGE
        or lon >= EAST_EDGE
        or lat < SOUTH_EDGE
        or lat >= NORTH_EDGE
    ):
        return None, None

    i = np.digitize(lon, XAXIS) - 1
    j = np.digitize(lat, YAXIS) - 1

    return i, j
