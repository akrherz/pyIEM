"""Multi-RADAR Multi-Sensor (MRMS) Helper Functions

Hopefully useful functions to help with the processing of MRMS data
"""
import numpy as np
import struct
import datetime
import pytz
import requests
import gzip
import os

WEST = -130.
EAST = -60.
NORTH = 55.
SOUTH = 20.
XAXIS = np.arange(WEST, EAST, 0.01)
YAXIS = np.arange(SOUTH, NORTH, 0.01)


def fetch(product, valid, tmpdir="/mesonet/tmp"):
    """Get a desired MRMS product

    Applies the following logic:
        - does the file exist in `tmpdir`?
        - can I fetch it from mtarchive?
        - if recent, can I fetch it from NOAA MRMS website

    Args:
      product(str): MRMS product type
      valid(datetime): Datetime object for desired timestamp
      tmpdir(str,optional): location to check/place the downloaded file
    """
    fn = "%s_00.00_%s00.grib2.gz" % (product,
                                     valid.strftime("%Y%m%d-%H%M"))
    tmpfn = "%s/%s" % (tmpdir, fn)
    # Option 1, we have this file already in cache!
    if os.path.isfile(tmpfn):
        return tmpfn
    # Option 2, go fetch it from mtarchive
    uri = ("http://mtarchive.geol.iastate.edu/%s/mrms/ncep/%s/%s"
           ) % (valid.strftime("%Y/%m/%d"), product, fn)
    try:
        req = requests.get(uri, timeout=30)
    except:
        req = None
    if req and req.status_code == 200:
        o = open(tmpfn, 'wb')
        o.write(req.content)
        o.close()
        return tmpfn
    # Option 3, we go look at MRMS website, if timestamp is recent
    utcnow = datetime.datetime.utcnow()
    if valid.tzinfo is not None:
        utcnow = utcnow.replace(tzinfo=pytz.utc)
    if (utcnow - valid).total_seconds() > 86400:
        # Can't do option 3!
        return None
    # Loop over all IDP data centers
    for center in ['', 'bldr.', 'cprk.']:
        uri = ("http://mrms.%sncep.noaa.gov/data/2D/%s/MRMS_%s"
               ) % (center, product, fn)
        try:
            req = requests.get(uri, timeout=30)
        except:
            req = None
        if req and req.status_code == 200:
            o = open(tmpfn, 'wb')
            o.write(req.content)
            o.close()
            return tmpfn
    return None


def make_colorramp():
    """
    Make me a crude color ramp
    """
    c = np.zeros((256, 3), np.int)

    # Ramp blue
    for b in range(0, 37):
        c[b, 2] = 255
    for b in range(37, 77):
        c[b, 2] = (77-b)*6
    for b in range(160, 196):
        c[b, 2] = (b-160)*6
    for b in range(196, 256):
        c[b, 2] = 254
    # Ramp Green up
    for g in range(0, 37):
        c[g, 1] = g*6
    for g in range(37, 116):
        c[g, 1] = 254
    for g in range(116, 156):
        c[g, 1] = (156-g)*6
    for g in range(196, 256):
        c[g, 1] = (g-196)*4
    # and Red
    for r in range(77, 117):
        c[r, 0] = (r-77)*6.
    for r in range(117, 256):
        c[r, 0] = 254

    # Gray for missing
    c[255, :] = [144, 144, 144]
    # Black to remove, eventually
    c[0, :] = [0, 0, 0]
    return tuple(c.ravel())


def reader(fn):
    ''' Return metadata and the data '''
    fp = gzip.open(fn, 'rb')
    metadata = {}
    (year, month, day, hour, minute, second, nx, ny, nz, _, _, _, _,
     _, _, _, _, ul_lon_cc, ul_lat_cc, _, scale_lon, scale_lat,
     grid_scale) = struct.unpack('9i4c10i', fp.read(80))

    metadata['ul_lon_cc'] = ul_lon_cc / float(scale_lon)
    metadata['ul_lat_cc'] = ul_lat_cc / float(scale_lat)
    # Calculate
    metadata['ll_lon_cc'] = metadata['ul_lon_cc']
    metadata['ll_lat_cc'] = metadata['ul_lat_cc'] - ((scale_lat /
                                                      float(grid_scale)) *
                                                     (ny - 1))
    metadata['ll_lat'] = metadata['ll_lat_cc'] - (scale_lat /
                                                  float(grid_scale)) / 2.0
    metadata['ul_lat'] = metadata['ul_lat_cc'] - (scale_lat /
                                                  float(grid_scale)) / 2.0
    metadata['ll_lon'] = metadata['ll_lon_cc'] - (scale_lon /
                                                  float(grid_scale)) / 2.0
    metadata['ul_lon'] = metadata['ul_lon_cc'] - (scale_lon /
                                                  float(grid_scale)) / 2.0

    metadata['valid'] = datetime.datetime(year, month, day, hour, minute,
                                          second).replace(
                                                tzinfo=pytz.timezone("UTC"))

    struct.unpack('%si' % (nz,), fp.read(nz*4))  # levels
    struct.unpack('i', fp.read(4))  # z_scale
    struct.unpack('10i', fp.read(40))  # bogus
    struct.unpack('20c', fp.read(20))  # varname
    metadata['unit'] = struct.unpack('6c', fp.read(6))
    var_scale, _, num_radars = struct.unpack('3i', fp.read(12))
    struct.unpack('%sc' % (num_radars*4,), fp.read(num_radars*4))  # rad_list
    # print unit, var_scale, miss_val
    sz = nx * ny * nz
    data = struct.unpack('%sh' % (sz,), fp.read(sz*2))
    data = np.reshape(np.array(data), (ny, nx)) / float(var_scale)
    # ma.masked_equal(data, miss_val)
    # print nx, ny, nz, levels, rad_list, len(data), data[1000], var_scale
    # print miss_val, np.shape(data)

    fp.close()
    return metadata, data


def get_fn(prefix, now, tile):
    ''' Get the filename for this timestamp and tile '''
    return now.strftime(('/mnt/a4/data/%Y/%m/%d/mrms/tile' + str(tile) +
                         '/'+prefix+'/'+prefix+'.%Y%m%d.%H%M00.gz'))


def write_worldfile(filename):
    """Write a worldfile to the given filename

    Args:
      filename (str): filename to write the world file information to
    """
    output = open(filename, 'w')
    output.write("""0.01
0.00
0.00
-0.01
%s
%s""" % (WEST, NORTH))
    output.close()
