"""Grid definitions for Stage IV data."""

from datetime import datetime, timezone
from typing import Optional

import numpy as np
from affine import Affine
from pyproj import Proj

DX, DY = 4_762.5, 4_762.5
NX = 1121
NY = 881
# This is the lower left corner edge of the grid (native Grib projection)
AFFINE_NATIVE = Affine(DX, 0.0, -1_904_912.924, 0.0, DY, -7_619_986.180)
# This is the affine for the netcdf file
AFFINE_NC = AFFINE_NATIVE
# This is the affine when the grid is flipped N/S
AFFINE = Affine(DX, 0.0, -1_904_912.924, 0.0, -DY, -3_424_223.680)
# This is the projection of the native Grib
PROJPARMS = {
    "a": 6_371_200.0,  # GDAL and pygrib disagree on this value
    "b": 6_371_200.0,  # using what pygrib says for 2024 file
    "proj": "stere",
    "lat_ts": 60.0,
    "lat_0": 90.0,
    "lon_0": -105.0,
}
PROJ = Proj(PROJPARMS)

# These are the grid cell centers
XAXIS = np.linspace(
    AFFINE_NATIVE.c + DX / 2.0, AFFINE_NATIVE.c + DX / 2.0 + (NX - 1) * DX, NX
)
YAXIS = np.linspace(
    AFFINE_NATIVE.f + DY / 2.0, AFFINE_NATIVE.f + DY / 2.0 + (NY - 1) * DY, NY
)

# Older stage IV grid definition
DX_OLD, DY_OLD = 4_763.0, 4_763.0
NX_OLD = 1160
NY_OLD = 880
# Lower Left edge of native grib files
AFFINE_NATIVE_OLD = Affine(
    DX_OLD, 0.0, -2_097_827.439, 0.0, DY_OLD, -7_622_315.608
)
# Upper left when flipped n/s
AFFINE_OLD = Affine(DX_OLD, 0.0, -2_097_827.439, 0.0, -DY_OLD, -3_430_875.608)

# This is the timestamp when the archive flips to modern grid
ARCHIVE_FLIP = datetime(2002, 1, 1, tzinfo=timezone.utc)


def find_ij(lon: float, lat: float) -> tuple[Optional[int], Optional[int]]:
    """Find the grid cell index for a given lon/lat (assuming modern grid)."""
    x, y = PROJ(lon, lat)  # skipcq
    i = int((x - AFFINE_NATIVE.c) / AFFINE_NATIVE.a)
    j = int((y - AFFINE_NATIVE.f) / AFFINE_NATIVE.e)
    if i < 0 or j < 0 or i >= NX or j >= NY:
        return None, None
    return i, j
