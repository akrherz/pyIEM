"""Support library for the IEM Reanalysis code

.. data:: SOUTH

    Latitude of the southern edge of the IEM Reanalysis.


"""
from __future__ import print_function
import datetime

import numpy as np
import pytz

# 1/4 degree grid, grid cell is the lower left corner
SOUTH = 36.0
WEST = -104.0
NORTH = 49.0
EAST = -80.5

DX = 0.25
DY = 0.25
NX = int((EAST - WEST) / DX)
NY = int((NORTH - SOUTH) / DY)
XAXIS = np.arange(WEST, EAST, DX)
YAXIS = np.arange(SOUTH, NORTH, DY)


def daily_offset(ts):
    """ Compute the timestamp index in the netcdf file """
    # In case ts is passed here as a datetime.date object
    ts = datetime.datetime(ts.year, ts.month, ts.day)
    base = ts.replace(month=1, day=1, hour=0, minute=0,
                      second=0, microsecond=0)
    days = (ts - base).days
    return int(days)


def hourly_offset(dtobj):
    """Return time index for given timestamp

    Args:
      dtobj (datetime): datetime, if no tzinfo, we assume it is UTC

    Returns:
      int time index in the netcdf file
    """
    if dtobj.tzinfo and dtobj.tzinfo != pytz.utc:
        dtobj = dtobj.astimezone(pytz.utc)
    base = dtobj.replace(month=1, day=1, hour=0, minute=0,
                         second=0, microsecond=0)
    seconds = (dtobj - base).total_seconds()
    return int(seconds / 3600.)


def find_ij(lon, lat):
    """ Compute which grid cell this lon, lat resides within
    """
    if lon < WEST or lon >= EAST or lat < SOUTH or lat >= NORTH:
        return None, None

    i = np.digitize([lon, ], XAXIS)[0] - 1
    j = np.digitize([lat, ], YAXIS)[0] - 1

    return i, j
