"""Support library for the IEM Reanalysis code

.. data:: SOUTH

    Latitude of the southern edge of the IEM Reanalysis.


"""
from datetime import datetime, timezone

import numpy as np
import xarray as xr
from affine import Affine
from psycopg.sql import SQL, Identifier
from rasterio.warp import Resampling, reproject

from pyiem.database import get_dbconn

# 1/8 degree grid, grid cell is the lower left corner
SOUTH = 23.0
WEST = -126.0
NORTH = 50.0
EAST = -65.0

DX = 0.125
DY = 0.125
# hard coding these to prevent flakey behaviour with dynamic computation
NX = 488  # int((EAST - WEST) / DX)
NY = 216  # int((NORTH - SOUTH) / DY)
XAXIS = np.arange(WEST, EAST, DX)
YAXIS = np.arange(SOUTH, NORTH, DY)
AFFINE = Affine(DX, 0.0, WEST, 0.0, 0 - DY, NORTH)
AFFINE_NATIVE = Affine(DX, 0.0, WEST, 0.0, DY, SOUTH)
MRMS_AFFINE = Affine(0.01, 0.0, WEST, 0.0, -0.01, NORTH)


def get_table(valid):
    """Figure out which table should be used for given valid.

    Args:
      valid (datetime or date):  which time is of interest

    Returns:
      str tablename
    """
    # careful here, a datetime is not an instance of date
    if isinstance(valid, datetime):
        table = f"iemre_hourly_{valid.astimezone(timezone.utc):%Y%m}"
    else:
        table = f"iemre_daily_{valid.year}"
    return table


def set_grids(valid, ds, table=None):
    """Update the database with a given ``xarray.Dataset``.

    Args:
      valid (datetime or date): If datetime, save hourly, if date, save daily
      ds (xarray.Dataset): The xarray dataset to save
      table (str,optional): hard coded database table to use to set the data
        on.  Usually dynamically computed.
    """
    table = Identifier(table if table is not None else get_table(valid))
    pgconn = get_dbconn("iemre")
    cursor = pgconn.cursor()
    # Do we currently have database entries?
    cursor.execute(
        SQL("SELECT valid from {} WHERE valid = %s LIMIT 1").format(table),
        (valid,),
    )
    if cursor.rowcount == 0:
        # Create entries
        cursor.execute(
            SQL(
                "insert into {}(gid, valid) select gid, %s from iemre_grid"
            ).format(table),
            (valid,),
        )
        cursor.close()
        pgconn.commit()
        cursor = pgconn.cursor()
    # Now we do our update.
    query = SQL("update {} set {} where valid = %s and gid = %s").format(
        table,
        SQL(",".join(f"{col} = %s" for col in ds)),
    )
    # Implementation notes: xarray iteration was ~25 secs, loading into memory
    # instead is a few seconds :/

    pig = {v: ds[v].values for v in ds}
    updated = 0
    for y in range(ds.sizes["y"]):
        for x in range(ds.sizes["x"]):
            arr = [pig[v][y, x] for v in ds]
            arr.extend([valid, y * NX + x])
            cursor.execute(query, arr)
            updated += 1
            if updated % 500 == 0:
                cursor.close()
                pgconn.commit()
                cursor = pgconn.cursor()

    # If we generate a cursor, we should save it
    cursor.close()
    pgconn.commit()


def get_grids(valid, varnames=None, cursor=None, table=None):
    """Fetch grid(s) from the database, returning xarray.

    Args:
      valid (datetime or date): If datetime, load hourly, if date, load daily
      varnames (str or list,optional): Which variables to fetch from database,
        defaults to all available
      cursor (database cursor,optional): cursor to use for query
      table (str,optional): Hard coded table to fetch data from, useful in the
        case of forecast data.

    Returns:
      ``xarray.Dataset``"""
    table = table if table is not None else get_table(valid)
    if cursor is None:
        pgconn = get_dbconn("iemre")
        cursor = pgconn.cursor()
    # rectify varnames
    if isinstance(varnames, str):
        varnames = [varnames]
    # Compute variable names
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s and "
        "column_name not in ('gid', 'valid')",
        (table,),
    )
    use_columns = []
    for row in cursor:
        if not varnames or row[0] in varnames:
            use_columns.append(row[0])
    colsql = ",".join(use_columns)
    cursor.execute(
        f"SELECT (gid / %s)::int as y, gid %% %s as x, {colsql} "
        f"from {table} WHERE valid = %s",
        (NX, NX, valid),
    )
    data = dict((key, np.full((NY, NX), np.nan)) for key in use_columns)
    for row in cursor:
        for i, col in enumerate(use_columns):
            data[col][row[0], row[1]] = row[2 + i]
    ds = xr.Dataset(
        dict((key, (["y", "x"], data[key])) for key in data),
        coords={"lon": (["x"], XAXIS), "lat": (["y"], YAXIS)},
    )
    return ds


def get_dailyc_ncname():
    """Return the filename of the daily climatology netcdf file"""
    return "/mesonet/data/iemre/iemre_dailyc.nc"


def get_daily_ncname(year):
    """Get the daily netcdf filename for the given year"""
    return f"/mesonet/data/iemre/{year}_iemre_daily.nc"


def get_dailyc_mrms_ncname():
    """Get the MRMS daily climatology filename"""
    return "/mesonet/data/mrms/mrms_dailyc.nc"


def get_daily_mrms_ncname(year):
    """Get the daily netcdf MRMS filename for the given year"""
    return f"/mesonet/data/mrms/{year}_mrms_daily.nc"


def get_hourly_ncname(year):
    """Get the daily netcdf filename for the given year"""
    return f"/mesonet/data/iemre/{year}_iemre_hourly.nc"


def daily_offset(ts):
    """Compute the timestamp index in the netcdf file"""
    # In case ts is passed here as a datetime.date object
    ts = datetime(ts.year, ts.month, ts.day)
    base = ts.replace(
        month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    days = (ts - base).days
    return int(days)


def hourly_offset(dtobj):
    """Return time index for given timestamp

    Args:
      dtobj (datetime): datetime, if no tzinfo, we assume it is UTC

    Returns:
      int time index in the netcdf file
    """
    if dtobj.tzinfo and dtobj.tzinfo != timezone.utc:
        dtobj = dtobj.astimezone(timezone.utc)
    base = dtobj.replace(
        month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    seconds = (dtobj - base).total_seconds()
    return int(seconds / 3600.0)


def find_ij(lon, lat):
    """Compute which grid cell this lon, lat resides within"""
    if lon < WEST or lon >= EAST or lat < SOUTH or lat >= NORTH:
        return None, None

    i = np.digitize([lon], XAXIS)[0] - 1
    j = np.digitize([lat], YAXIS)[0] - 1

    return i, j


def get_gid(lon, lat):
    """Compute the grid id for the given location."""
    i, j = find_ij(lon, lat)
    if i is None:
        return None
    return j * NX + i


def reproject2iemre(grid, affine_in, crs_in, resampling=None, dst_nodata=None):
    """Reproject the given grid to IEMRE grid, returning S to N oriented grid.

    Note: If the affine_in is dy > 0 then the grid is assumed to be S to N.

    Args:
        grid (numpy.array): 2D grid to reproject
        affine_in (affine.Affine): affine transform of input grid
        crs_in (pyproj.Proj): projection of input grid
        resampling (rasterio.warp.Resampling,optional): defaults to nearest
        dst_nodata (float,optional): defaults to np.nan

    Returns:
        numpy.array of reprojected grid oriented S to N like IEMRE
    """
    data = np.zeros((NY, NX), float)
    reproject(
        grid,
        data,
        src_transform=affine_in,
        src_crs=crs_in,
        dst_transform=AFFINE if affine_in.e < 0 else AFFINE_NATIVE,
        dst_crs={"init": "EPSG:4326"},
        dst_nodata=dst_nodata if dst_nodata is not None else np.nan,
        resampling=(
            resampling if resampling is not None else Resampling.nearest
        ),
    )
    return data if affine_in.e > 0 else np.flipud(data)
