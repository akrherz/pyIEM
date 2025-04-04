"""Multi-RADAR Multi-Sensor (MRMS) Helper Functions.

Hopefully useful functions to help with the processing of MRMS data
"""

import gzip
import os
import struct
from datetime import datetime, timezone
from typing import Optional

import httpx
import numpy as np
from affine import Affine

from pyiem.util import LOG

# NOTE: This is the info for the MRMS grib products, NOT the IEM netcdf
# This is the center of the corner pixels
WEST = -129.995
NORTH = 54.995
SOUTH = 20.005
EAST = -60.005
DX = 0.01
DY = 0.01
NX = 7000
NY = 3500

# These are the edges of the domain
WEST_EDGE = -130.0
EAST_EDGE = -60.0
NORTH_EDGE = 55.0
SOUTH_EDGE = 20.0
XAXIS = np.linspace(WEST, EAST, NX)
YAXIS = np.linspace(SOUTH, NORTH, NY)
AFFINE = Affine(0.01, 0.0, WEST_EDGE, 0.0, -0.01, NORTH_EDGE)

# NOTE: These are the values for the IEM netcdf files, a smaller domain
MRMS4IEMRE_WEST_EDGE = -126.0
MRMS4IEMRE_EAST_EDGE = -65.0
MRMS4IEMRE_NORTH_EDGE = 50.0
MRMS4IEMRE_SOUTH_EDGE = 23.0
MRMS4IEMRE_WEST = -125.995
MRMS4IEMRE_EAST = -65.005
MRMS4IEMRE_NORTH = 49.995
MRMS4IEMRE_SOUTH = 23.005
MRMS4IEMRE_DX = 0.01
MRMS4IEMRE_DY = 0.01
MRMS4IEMRE_NX = 6100
MRMS4IEMRE_NY = 2700
MRMS4IEMRE_AFFINE = Affine(
    DX, 0.0, MRMS4IEMRE_WEST_EDGE, 0.0, -DY, MRMS4IEMRE_NORTH_EDGE
)
# How the netcdf files are stored
MRMS4IEMRE_AFFINE_NC = Affine(
    DX, 0.0, MRMS4IEMRE_WEST_EDGE, 0.0, DY, MRMS4IEMRE_SOUTH_EDGE
)
MRMS4IEMRE_XAXIS = np.linspace(MRMS4IEMRE_WEST, MRMS4IEMRE_EAST, MRMS4IEMRE_NX)
MRMS4IEMRE_YAXIS = np.linspace(
    MRMS4IEMRE_SOUTH, MRMS4IEMRE_NORTH, MRMS4IEMRE_NY
)


def find_ij(lon: float, lat: float) -> tuple[Optional[int], Optional[int]]:
    """CAUTION: This is for the netcdf files, not grib2 files."""
    if (
        lon < MRMS4IEMRE_WEST_EDGE
        or lon >= MRMS4IEMRE_EAST_EDGE
        or lat < MRMS4IEMRE_SOUTH_EDGE
        or lat >= MRMS4IEMRE_NORTH_EDGE
    ):
        return None, None
    j = int((lat - MRMS4IEMRE_SOUTH_EDGE) / DY)
    i = int((lon - MRMS4IEMRE_WEST_EDGE) / DX)
    return i, j


def is_gzipped(text):
    """Check that we have gzipped content."""
    return text[:2] == b"\x1f\x8b"


def get_url(center, valid, product):
    """Return the URL given the provided options."""
    fn = f"{product}_00.00_{valid:%Y%m%d-%H%M}00.grib2.gz"
    if center == "mtarchive":
        uri = (
            f"https://mtarchive.geol.iastate.edu/{valid:%Y/%m/%d}"
            f"/mrms/ncep/{product}/{fn}"
        )
        if 2000 < valid.year < 2012 and product == "PrecipRate":
            uri = (
                f"https://mtarchive.geol.iastate.edu/{valid:%Y/%m/%d}"
                f"/mrms/reanalysis/{product}/{fn}"
            )
    else:
        uri = f"https://mrms{center}.ncep.noaa.gov/2D/{product}/MRMS_{fn}"
    return uri


def fetch(product, valid: datetime, tmpdir="/mesonet/tmp"):
    """Get a desired MRMS product.

    Applies the following logic:
        - does the file exist in `tmpdir`?
        - can I fetch it from mtarchive?
        - if recent, can I fetch it from NOAA MRMS website

    Args:
      product(str): MRMS product type
      valid(datetime): Datetime object for desired timestamp
      tmpdir(str,optional): location to check/place the downloaded file
    """
    fn = f"{product}_00.00_{valid:%Y%m%d-%H%M}00.grib2.gz"
    tmpfn = os.path.join(tmpdir, fn)
    # Option 1, we have this file already in cache!
    if os.path.isfile(tmpfn):
        LOG.info("Found %s in tmpdir cache", tmpfn)
        return tmpfn
    # Option 2, go fetch it from mtarchive
    url = get_url("mtarchive", valid, product)
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        LOG.info("Failed to fetch %s", url)
        resp = None
    if resp and is_gzipped(resp.content):
        with open(tmpfn, "wb") as fd:
            fd.write(resp.content)
        return tmpfn
    # Option 3, we go look at MRMS website, if timestamp is recent
    utcnow = datetime.now(timezone.utc)
    if valid.tzinfo is None:
        utcnow = utcnow.replace(tzinfo=None)
    if (utcnow - valid).total_seconds() > 86400:
        # Can't do option 3!
        return None
    # Loop over all IDP data centers
    for center in ["", "-bldr", "-cprk"]:
        url = get_url(center, valid, product)
        try:
            resp = httpx.get(url, timeout=30)
            resp.raise_for_status()
        except Exception:
            LOG.info("Failed to fetch %s", url)
            resp = None
        if resp and is_gzipped(resp.content):
            with open(tmpfn, "wb") as fd:
                fd.write(resp.content)
            return tmpfn
    return None


def make_colorramp():
    """Make me a crude color ramp."""
    c = np.zeros((256, 3), int)

    # Ramp blue
    for b in range(0, 37):
        c[b, 2] = 255
    for b in range(37, 77):
        c[b, 2] = (77 - b) * 6
    for b in range(160, 196):
        c[b, 2] = (b - 160) * 6
    for b in range(196, 256):
        c[b, 2] = 254
    # Ramp Green up
    for g in range(0, 37):
        c[g, 1] = g * 6
    for g in range(37, 116):
        c[g, 1] = 254
    for g in range(116, 156):
        c[g, 1] = (156 - g) * 6
    for g in range(196, 256):
        c[g, 1] = (g - 196) * 4
    # and Red
    for r in range(77, 117):
        c[r, 0] = (r - 77) * 6.0
    for r in range(117, 256):
        c[r, 0] = 254

    # Gray for missing
    c[255, :] = [144, 144, 144]
    # Black to remove, eventually
    c[0, :] = [0, 0, 0]
    return tuple(c.ravel())


def reader(fn):
    """Return metadata and the data."""
    fp = gzip.open(fn, "rb")
    metadata = {}
    (
        year,
        month,
        day,
        hour,
        minute,
        second,
        nx,
        ny,
        nz,
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        ul_lon_cc,
        ul_lat_cc,
        _,
        scale_lon,
        scale_lat,
        grid_scale,
    ) = struct.unpack("9i4c10i", fp.read(80))

    metadata["ul_lon_cc"] = ul_lon_cc / float(scale_lon)
    metadata["ul_lat_cc"] = ul_lat_cc / float(scale_lat)
    # Calculate
    metadata["ll_lon_cc"] = metadata["ul_lon_cc"]
    metadata["ll_lat_cc"] = metadata["ul_lat_cc"] - (
        (scale_lat / float(grid_scale)) * (ny - 1)
    )
    metadata["ll_lat"] = (
        metadata["ll_lat_cc"] - (scale_lat / float(grid_scale)) / 2.0
    )
    metadata["ul_lat"] = (
        metadata["ul_lat_cc"] - (scale_lat / float(grid_scale)) / 2.0
    )
    metadata["ll_lon"] = (
        metadata["ll_lon_cc"] - (scale_lon / float(grid_scale)) / 2.0
    )
    metadata["ul_lon"] = (
        metadata["ul_lon_cc"] - (scale_lon / float(grid_scale)) / 2.0
    )

    metadata["valid"] = datetime(
        year, month, day, hour, minute, second
    ).replace(tzinfo=timezone.utc)

    struct.unpack(f"{nz}i", fp.read(nz * 4))  # levels
    struct.unpack("i", fp.read(4))  # z_scale
    struct.unpack("10i", fp.read(40))  # bogus
    struct.unpack("20c", fp.read(20))  # varname
    metadata["unit"] = struct.unpack("6c", fp.read(6))
    var_scale, _, num_radars = struct.unpack("3i", fp.read(12))
    struct.unpack(f"{num_radars * 4}c", fp.read(num_radars * 4))  # rad_list
    sz = nx * ny * nz
    data = struct.unpack(f"{sz}h", fp.read(sz * 2))
    data = np.reshape(np.array(data), (ny, nx)) / float(var_scale)

    fp.close()
    return metadata, data


def write_worldfile(filename):
    """Write a worldfile to the given filename.

    Args:
      filename (str): filename to write the world file information to
    """
    # World file defines the center of the upper left pixel
    with open(filename, "w", encoding="utf8") as fd:
        fd.write(f"0.01\n0.00\n0.00\n-0.01\n{WEST}\n{NORTH}")
