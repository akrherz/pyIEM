"""
Support library for the IEM Reanalysis code
"""
import numpy

# 1/4 degree grid, grid cell is the lower left corner
SOUTH = 36.0
WEST = -104.0
NORTH = 49.0
EAST = -80.5

DX = 0.25
DY = 0.25
NX = int( (EAST - WEST) / DX )
NY = int( (NORTH - SOUTH) / DY )
XAXIS = numpy.arange(WEST, EAST, DX)
YAXIS = numpy.arange(SOUTH, NORTH, DY)

def daily_offset(ts):
    """ Compute the timestamp index in the netcdf file """
    base = ts.replace(month=1,day=1,hour=0,minute=0,second=0,microsecond=0)
    days = (ts - base).days
    return int(days)

def hourly_offset(ts):
    """ Compute the timestamp index in the netcdf file """
    base = ts.replace(month=1,day=1,hour=0,minute=0,second=0,microsecond=0)
    days = (ts - base).days
    seconds = (ts - base).seconds
    return int(int(days) * 24.0 + seconds / 3600.)

def find_ij(lon, lat):
    """ Compute which grid cell this lon, lat resides within
    """
    if lon < WEST or lon >= EAST or lat < SOUTH or lat >= NORTH:
        return None, None
    
    i = numpy.digitize([lon,], XAXIS)[0] - 1
    j = numpy.digitize([lat,], YAXIS)[0] - 1
    
    return i, j