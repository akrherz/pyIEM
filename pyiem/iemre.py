"""Support library for the IEM Reanalysis code

.. data:: SOUTH

    Latitude of the southern edge of the IEM Reanalysis.


"""
from __future__ import print_function
import datetime

from affine import Affine
import numpy as np
import pytz

# 1/8 degree grid, grid cell is the lower left corner
SOUTH = 23.0
WEST = -126.0
NORTH = 50.0
EAST = -65.0

DX = 0.125
DY = 0.125
NX = int((EAST - WEST) / DX)
NY = int((NORTH - SOUTH) / DY)
XAXIS = np.arange(WEST, EAST, DX)
YAXIS = np.arange(SOUTH, NORTH, DY)
AFFINE = Affine(DX,
                0.,
                WEST,
                0.,
                0 - DY,
                NORTH)
MRMS_AFFINE = Affine(0.01,
                     0.,
                     WEST,
                     0.,
                     -0.01,
                     NORTH)


def get_dailyc_ncname():
    """Return the filename of the daily climatology netcdf file"""
    return "/mesonet/data/iemre/iemre_dailyc.nc"


def get_daily_ncname(year):
    """Get the daily netcdf filename for the given year"""
    return "/mesonet/data/iemre/%s_iemre_daily.nc" % (year, )


def get_dailyc_mrms_ncname():
    """Get the MRMS daily climatology filename"""
    return "/mesonet/data/iemre/iemre_mrms_dailyc.nc"


def get_daily_mrms_ncname(year):
    """Get the daily netcdf MRMS filename for the given year"""
    return "/mesonet/data/iemre/%s_iemre_mrms_daily.nc" % (year, )


def get_hourly_ncname(year):
    """Get the daily netcdf filename for the given year"""
    return "/mesonet/data/iemre/%s_iemre_hourly.nc" % (year, )


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
