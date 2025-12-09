"""test IEMRE stuff"""

import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pygrib
from affine import Affine

from pyiem import database, iemre
from pyiem.util import get_test_filepath, utc


def test_axis_size():
    """Ensure that our legacy axis sizes are correct."""
    assert iemre.NX == len(iemre.XAXIS)
    assert iemre.NY == len(iemre.YAXIS)


def test_d2l():
    """Test our logic."""
    assert iemre.d2l("europe") == "iemre_europe"


def test_grb2iemre():
    """Test that we can take a grib file and do magic."""
    grbs = pygrib.open(get_test_filepath("grib/hrrr_srad.grib2"))
    res = iemre.grb2iemre(grbs[1])
    assert res.shape == (iemre.NY, iemre.NX)


def test_reproject_masked_array():
    """Test that we can handle an input masked array."""
    # 30 km grid over Iowa 520km x 360km
    affine_in = Affine(30000.0, 0.0, 202050.0, 0.0, 30000.0, 4470000.0)
    crs_in = {"init": "epsg:26915"}
    vals = np.ma.array(np.ones((12, 17)), mask=True)
    res = iemre.reproject2iemre(vals, affine_in, crs_in)
    # get value for Ames Iowa
    i, j = iemre.find_ij(-93.62, 42.02)
    assert res.mask[j, i]


def test_reproject_epsg26915_iowa_to_iemre_sn():
    """Test that a bunch of ones over Iowa get reprojected to IEMRE."""
    # 30 km grid over Iowa 520km x 360km
    affine_in = Affine(30000.0, 0.0, 202050.0, 0.0, 30000.0, 4470000.0)
    crs_in = {"init": "epsg:26915"}
    res = iemre.reproject2iemre(np.ones((12, 17)), affine_in, crs_in)
    # get value for Ames Iowa
    i, j = iemre.find_ij(-93.62, 42.02)
    assert res[j, i] == 1.0
    # get value for St Louis Missouri
    i, j = iemre.find_ij(-90.20, 38.63)
    assert res.mask[j, i]
    # get value for Minneapolis Minnesota
    i, j = iemre.find_ij(-93.26, 44.98)
    assert res.mask[j, i]


def test_reproject_epsg26915_iowa_to_iemre():
    """Test that a bunch of ones over Iowa get reprojected to IEMRE."""
    # 30 km grid over Iowa 520km x 360km
    affine_in = Affine(30000.0, 0.0, 202050.0, 0.0, -30000.0, 5000000.0)
    crs_in = {"init": "epsg:26915"}
    res = iemre.reproject2iemre(np.ones((12, 17)), affine_in, crs_in)
    # get value for Ames Iowa
    i, j = iemre.find_ij(-93.62, 42.02)
    assert res[j, i] == 1.0
    # get value for St Louis Missouri
    i, j = iemre.find_ij(-90.20, 38.63)
    assert res.mask[j, i]


def test_reproject():
    """Test the iemre.reproject2iemre."""
    affine_in = Affine(0.2, 0.0, -126.0, 0.0, -0.2, 50.0)
    crs_in = {"init": "epsg:4326"}
    res = iemre.reproject2iemre(np.ones((100, 100)), affine_in, crs_in)
    assert res.shape == (iemre.NY, iemre.NX)
    assert np.nanmax(res) == 1.0


def test_api():
    """Test some aux methods."""
    assert iemre.get_dailyc_mrms_ncname() is not None
    assert iemre.get_dailyc_ncname() is not None


def test_ncname():
    """Test the responses for get_names."""
    assert iemre.get_daily_ncname(2020) is not None
    assert iemre.get_hourly_ncname(2020) is not None
    assert iemre.get_daily_mrms_ncname(2020) is not None


def test_get_table():
    """Test get_table."""
    d1 = datetime.date(2000, 8, 1)
    assert iemre.get_table(d1) == "iemre_daily_2000"
    d2 = utc(2000, 9, 1, 12)
    assert iemre.get_table(d2) == "iemre_hourly_200009"


def test_get_domain():
    """Test the get_domain method."""
    assert iemre.get_domain(100, 30) == "china"
    assert iemre.get_domain(-1000, 30) is None


def test_get_gid():
    """Can we get a gid?"""
    assert iemre.get_gid(-96, 44) is not None
    assert iemre.get_gid(-960, 440) is None


def test_get_grids_no_domain():
    """Test that get_grids works without specifying a domain."""
    valid = datetime.date.today() + datetime.timedelta(days=120)
    assert iemre.get_grids(valid, varnames=["high_tmpk"])


def test_writing_grids():
    """Test letting the API write data from the future."""
    domain = "china"
    pgconn = database.get_dbconn(iemre.d2l(domain))
    cursor = pgconn.cursor()
    valid = datetime.date.today() + datetime.timedelta(days=120)
    ds = iemre.get_grids(valid, varnames=["high_tmpk"], domain=domain)
    # Set a sentinel value to see if it approximately round-trips
    sentinel = 251
    ds["high_tmpk"].values[140, 130] = sentinel
    iemre.set_grids(valid, ds, domain=domain)
    ds = iemre.get_grids(valid, varnames=["high_tmpk"], domain=domain)
    assert abs(ds["high_tmpk"].values[140, 130] - sentinel) < 0.1
    assert ds["high_tmpk"].lat[0] > 0
    # Cleanup after ourself
    cursor.execute(
        f"DELETE from iemre_daily_{valid:%Y} WHERE valid = %s",
        (valid,),
    )
    cursor.close()
    pgconn.commit()


def test_simple():
    """Get nulls for right and top values"""
    i, j = iemre.find_ij(iemre.EAST_EDGE, iemre.NORTH_EDGE)
    assert i is None
    assert j is None

    i, j = iemre.find_ij(iemre.WEST, iemre.SOUTH)
    assert i == 0
    assert j == 0


def test_hourly_offset():
    """Compute the offsets"""
    ts = utc(2013, 1, 1, 0, 0)
    offset = iemre.hourly_offset(ts)
    assert offset == 0

    ts = utc(2013, 1, 1, 6, 0)
    ts = ts.astimezone(ZoneInfo("America/Chicago"))
    offset = iemre.hourly_offset(ts)
    assert offset == 6

    ts = utc(2013, 1, 5, 12, 0)
    offset = iemre.hourly_offset(ts)
    assert offset == 4 * 24 + 12


def test_daily_offset():
    """Compute the offsets"""
    ts = utc(2013, 1, 1, 0, 0)
    offset = iemre.daily_offset(ts)
    assert offset == 0

    ts = datetime.date(2013, 2, 1)
    offset = iemre.daily_offset(ts)
    assert offset == 31

    ts = utc(2013, 1, 5, 12, 0)
    offset = iemre.daily_offset(ts)
    assert offset == 4
