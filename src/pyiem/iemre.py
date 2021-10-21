"""Support library for the IEM Reanalysis code

.. data:: SOUTH

    Latitude of the southern edge of the IEM Reanalysis.


"""
import string
import random
from datetime import timezone, datetime

from affine import Affine
import numpy as np
import xarray as xr
from pyiem.util import get_dbconn

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
        table = "iemre_hourly_%s" % (
            valid.astimezone(timezone.utc).strftime("%Y%m"),
        )
    else:
        table = f"iemre_daily_{valid.year}"
    return table


def set_grids(valid, ds, cursor=None, table=None):
    """Update the database with a given ``xarray.Dataset``.

    Args:
      valid (datetime or date): If datetime, save hourly, if date, save daily
      ds (xarray.Dataset): The xarray dataset to save
      cursor (database cursor, optional): cursor to use for queries
      table (str,optional): hard coded database table to use to set the data
        on.  Usually dynamically computed.
    """
    table = table if table is not None else get_table(valid)
    commit = cursor is None
    if cursor is None:
        pgconn = get_dbconn("iemre")
        cursor = pgconn.cursor()
    # see that we have database entries, otherwise create them
    cursor.execute(
        f"SELECT valid from {table} WHERE valid = %s LIMIT 1", (valid,)
    )
    insertmode = True
    if cursor.rowcount == 1:
        # Update mode, we do some massive tricks :/
        temptable = "".join(random.choices(string.ascii_uppercase, k=24))
        insertmode = False
        update_cols = ", ".join(
            ["%s = $%i" % (v, i + 1) for i, v in enumerate(ds)]
        )
        arg = "$%i" % (len(ds) + 1,)
        # approximate table size is 10 MB
        cursor.execute("SET temp_buffers = '100MB'")
        cursor.execute(
            f"CREATE UNLOGGED TABLE {temptable} AS SELECT * from {table} "
            f"WHERE valid = '{valid}'"
        )
        cursor.execute(f"CREATE INDEX on {temptable}(gid)")
        cursor.execute(
            (
                f"PREPARE pyiem_iemre_plan as UPDATE {temptable} "
                f"SET {update_cols} WHERE gid = {arg}"
            )
        )
    else:
        # Insert mode
        insert_cols = ", ".join(["%s" % (v,) for v in ds])
        percents = ", ".join(["$%i" % (i + 2,) for i in range(len(ds))])
        cursor.execute(
            f"PREPARE pyiem_iemre_plan as INSERT into {table} "
            f"(gid, valid, {insert_cols}) VALUES($1, '{valid}', {percents})"
        )
    sql = "execute pyiem_iemre_plan (%s)" % (",".join(["%s"] * (len(ds) + 1)),)

    def _n(val):
        """Prevent nan"""
        return None if np.isnan(val) else float(val)

    # Implementation notes: xarray iteration was ~25 secs, loading into memory
    # instead is a few seconds :/
    pig = {v: ds[v].values for v in ds}
    for y in range(ds.dims["y"]):
        for x in range(ds.dims["x"]):
            arr = [_n(pig[v][y, x]) for v in ds]
            if insertmode:
                arr.insert(0, y * NX + x)
            else:
                arr.append(y * NX + x)
            cursor.execute(sql, arr)
    if not insertmode:
        # Undo our hackery above
        cursor.execute(f"DELETE from {table} WHERE valid = '{valid}'")
        cursor.execute(f"INSERT into {table} SELECT * from {temptable}")
        cursor.execute(f"DROP TABLE {temptable}")
    # If we generate a cursor, we should save it
    if commit:
        cursor.close()
        pgconn.commit()
    else:
        cursor.execute("""DEALLOCATE pyiem_iemre_plan""")


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
