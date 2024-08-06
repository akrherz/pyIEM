"""Support library for the IEM Reanalysis code

.. data:: SOUTH

    Latitude of the southern edge of the IEM Reanalysis.


"""

from datetime import datetime, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pyproj
import xarray as xr
from affine import Affine
from psycopg.sql import SQL, Identifier
from rasterio.warp import Resampling, reproject

from pyiem.database import get_dbconn
from pyiem.util import LOG, utc

# Legacy constants prior to addition of other IEMRE domains
# 1/8 degree grid, grid cell is the lower left corner
SOUTH = 23.0
WEST = -126.0
NORTH = 50.0
EAST = -65.0
DX = 0.125
DY = 0.125
NX = 488
NY = 216
XAXIS = np.arange(WEST, EAST, DX)
YAXIS = np.arange(SOUTH, NORTH, DY)
AFFINE = Affine(DX, 0.0, WEST, 0.0, 0 - DY, NORTH)
AFFINE_NATIVE = Affine(DX, 0.0, WEST, 0.0, DY, SOUTH)
MRMS_AFFINE = Affine(0.01, 0.0, WEST, 0.0, -0.01, NORTH)

# Definition of analysis domains for IEMRE
DOMAINS = {
    "": {
        "west": WEST,
        "east": EAST,
        "south": SOUTH,
        "north": NORTH,
        "nx": NX,
        "ny": NY,
        "affine": AFFINE,
        "affine_native": AFFINE_NATIVE,
        "tzinfo": ZoneInfo("America/Chicago"),
    },
    "china": {
        "west": 70,
        "east": 140,
        "south": 15,
        "north": 55,
        "nx": 560,
        "ny": 320,
        "affine": Affine(DX, 0.0, 70, 0.0, 0 - DY, 55),
        "affine_native": Affine(DX, 0.0, 70, 0.0, DY, 15),
        "tzinfo": ZoneInfo("Asia/Shanghai"),
    },
    "europe": {
        "west": -10,
        "east": 40,
        "south": 35,
        "north": 70,
        "nx": 400,
        "ny": 280,
        "affine": Affine(DX, 0.0, -10, 0.0, 0 - DY, 70),
        "affine_native": Affine(DX, 0.0, -10, 0.0, DY, 35),
        "tzinfo": ZoneInfo("Europe/Paris"),
    },
}


def d2l(val) -> str:
    """Convert a domain label to a string used within filenames."""
    if val is None or val == "":
        return "iemre"
    return f"iemre_{val}"


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


def set_grids(valid, ds, table=None, domain: str = ""):
    """Update the database with a given ``xarray.Dataset``.

    Args:
      valid (datetime or date): If datetime, save hourly, if date, save daily
      ds (xarray.Dataset): The xarray dataset to save
      table (str,optional): hard coded database table to use to set the data
        on.  Usually dynamically computed.
      domain (str,optional): IEMRE domain to save data to
    """
    table = Identifier(table if table is not None else get_table(valid))
    dom = DOMAINS[domain]
    pgconn = get_dbconn(d2l(domain))
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
        # NB: whatever reason, postgresql is having a hard time with the query
        # plan on these newly inserted rows, so we force a vacuum analyze
        pgconn.autocommit = True
        pgconn.execute(SQL("VACUUM ANALYZE {}").format(table))
        pgconn.autocommit = False
        cursor = pgconn.cursor()

    # Now we do our update.
    query = SQL("update {} set {} where valid = %s and gid = %s").format(
        table,
        SQL(",".join(f"{col} = %s" for col in ds)),
    )

    # Implementation notes: seems quite fast
    pig = {v: ds[v].values.ravel().tolist() for v in ds}
    pig["valid"] = [f"{valid:%Y-%m-%d}"] * (dom["nx"] * dom["ny"])
    pig["gid"] = list(range(dom["nx"] * dom["ny"]))

    sts = utc()
    cursor.executemany(query, zip(*pig.values()))
    cursor.close()
    pgconn.commit()
    LOG.info(
        "timing %.2f/s", dom["nx"] * dom["ny"] / (utc() - sts).total_seconds()
    )


def get_grids(valid, varnames=None, cursor=None, table=None, domain: str = ""):
    """Fetch grid(s) from the database, returning xarray.

    Args:
      valid (datetime or date): If datetime, load hourly, if date, load daily
      varnames (str or list,optional): Which variables to fetch from database,
        defaults to all available
      cursor (database cursor,optional): cursor to use for query
      table (str,optional): Hard coded table to fetch data from, useful in the
        case of forecast data.
      domain (str,optional): IEMRE domain to fetch data from

    Returns:
      ``xarray.Dataset``"""
    table = table if table is not None else get_table(valid)
    dom = DOMAINS[domain]
    if cursor is None:
        pgconn = get_dbconn(d2l(domain))
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
            use_columns.append(row[0])  # noqa
    colsql = ",".join(use_columns)
    cursor.execute(
        f"SELECT (gid / %s)::int as y, gid %% %s as x, {colsql} "
        f"from {table} WHERE valid = %s",
        (dom["nx"], dom["nx"], valid),
    )
    data = {
        key: np.full((dom["ny"], dom["nx"]), np.nan) for key in use_columns
    }
    for row in cursor:
        for i, col in enumerate(use_columns):
            data[col][row[0], row[1]] = row[2 + i]
    ds = xr.Dataset(
        dict((key, (["y", "x"], data[key])) for key in data),
        coords={
            "lon": (["x"], np.arange(dom["west"], dom["east"], DX)),
            "lat": (["y"], np.arange(dom["south"], dom["north"], DY)),
        },
    )
    return ds


def get_dailyc_ncname(domain: str = "") -> str:
    """Return the filename of the daily climatology netcdf file"""
    return f"/mesonet/data/{d2l(domain)}/{d2l(domain)}_dailyc.nc"


def get_daily_ncname(year, domain: str = "") -> str:
    """Get the daily netcdf filename for the given year"""
    return f"/mesonet/data/{d2l(domain)}/{year}_{d2l(domain)}_daily.nc"


def get_dailyc_mrms_ncname():
    """Get the MRMS daily climatology filename"""
    return "/mesonet/data/mrms/mrms_dailyc.nc"


def get_daily_mrms_ncname(year):
    """Get the daily netcdf MRMS filename for the given year"""
    return f"/mesonet/data/mrms/{year}_mrms_daily.nc"


def get_hourly_ncname(year, domain: str = "") -> str:
    """Get the daily netcdf filename for the given year"""
    return f"/mesonet/data/{d2l(domain)}/{year}_{d2l(domain)}_hourly.nc"


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


def find_ij(lon, lat, domain: str = "") -> Tuple[Optional[int], Optional[int]]:
    """Compute which grid cell this lon, lat resides within"""
    dom = DOMAINS[domain]
    if (
        lon < dom["west"]
        or lon >= dom["east"]
        or lat < dom["south"]
        or lat >= dom["north"]
    ):
        return None, None

    i = np.digitize(lon, np.arange(dom["west"], dom["east"], DX)) - 1
    j = np.digitize(lat, np.arange(dom["south"], dom["north"], DY)) - 1

    return i, j


def get_domain(lon: float, lat: float) -> Optional[str]:
    """Compute the domain that contains the given point."""
    for domain, dom in DOMAINS.items():
        if (
            dom["west"] <= lon < dom["east"]
            and dom["south"] <= lat < dom["north"]
        ):
            return domain
    return None


def get_gid(lon, lat, domain: str = "") -> Optional[int]:
    """Compute the grid id for the given location."""
    i, j = find_ij(lon, lat, domain)
    if i is None:
        return None
    return j * DOMAINS[domain]["nx"] + i


def grb2iemre(grb, resampling=None, domain: str = "") -> np.ndarray:
    """Reproject a grib message onto the IEMRE grid.

    A helper frontend to ``reproject2iemre``.

    Args:
        grb (pygrib.gribmessage): single message to reproject
        resampling (rasterio.warp.Resampling,optional): defaults to nearest
        domain (str): IEMRE domain to reproject onto

    Returns:
        numpy.ma.array of reprojected grid oriented S to N like IEMRE
    """
    pparams = grb.projparams
    lat1 = grb["latitudeOfFirstGridPointInDegrees"]
    lon1 = grb["longitudeOfFirstGridPointInDegrees"]
    llx, lly = pyproj.Proj(pparams)(lon1, lat1)
    # NB: likely making assumptions that will fail, sometimes
    aff = Affine(
        grb["DxInMetres"],
        0.0,
        llx,
        0.0,
        -grb["DyInMetres"],
        lly + grb["DyInMetres"] * grb["Ny"],
    )
    return reproject2iemre(
        np.flipud(grb.values), aff, pparams, resampling, domain
    )


def reproject2iemre(
    grid, affine_in, crs_in: str, resampling=None, domain: str = ""
):
    """Reproject the given grid to IEMRE grid, returning S to N oriented grid.

    Note: If the affine_in is dy > 0 then the grid is assumed to be S to N.

    Args:
        grid (numpy.array): 2D grid to reproject
        affine_in (affine.Affine): affine transform of input grid
        crs_in (pyproj.Proj): projection of input grid
        resampling (rasterio.warp.Resampling,optional): defaults to nearest
        domain (str): IEMRE domain to reproject onto

    Returns:
        numpy.ma.array of reprojected grid oriented S to N like IEMRE
    """
    dom = DOMAINS[domain]
    data = np.zeros((dom["ny"], dom["nx"]), float)
    # If source is a masked array, we need to fill it
    src_is_masked = hasattr(grid, "mask")
    if src_is_masked:
        grid = grid.filled(np.nan)
    reproject(
        grid,
        data,
        src_transform=affine_in,
        src_crs=crs_in,
        dst_transform=(
            dom["affine"] if affine_in.e < 0 else dom["affine_native"]
        ),
        dst_crs={"init": "EPSG:4326"},
        dst_nodata=np.nan,
        resampling=(
            resampling if resampling is not None else Resampling.nearest
        ),
    )
    data = np.ma.array(data, mask=np.isnan(data))
    return data if affine_in.e > 0 else np.flipud(data)
