"""Helper for PRISM BIL data"""
import datetime

import numpy as np

NX = 1405
NY = 621

# This is the center of the upper left pixel
NORTH = 49.92
SOUTH = 24.04
WEST = -125.0
EAST = -66.46
DX = 0.0417
DY = 0.0417

XAXIS = WEST + np.arange(NX) * DX
YAXIS = SOUTH + np.arange(NY) * DY


def daily_offset(ts):
    """Compute the timestamp index in the netcdf file"""
    # In case ts is passed here as a datetime.date object
    ts = datetime.datetime(ts.year, ts.month, ts.day)
    return int((ts - ts.replace(month=1, day=1)).days)


def find_ij(lon, lat):
    """Compute which grid cell this lon, lat resides within"""
    if lon < WEST or lon >= EAST or lat < SOUTH or lat >= NORTH:
        return None, None

    i = np.digitize([lon], XAXIS)[0] - 1
    j = np.digitize([lat], YAXIS)[0] - 1

    return i, j
