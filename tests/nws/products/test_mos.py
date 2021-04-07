"""Test MOS Parsing."""

import pytest
from pyiem.nws.products.mos import parser as mosparser
from pyiem.util import utc, get_test_file


@pytest.mark.parametrize("z", ["12", "15", "21"])
def test_210407_negative_dates(z):
    """Test that we can get the timestamps right, le sigh."""
    utcnow = utc(2021, 4, 7, 15)
    prod = mosparser(get_test_file(f"MOS/NBS_{z}Z.txt"), utcnow=utcnow)
    sect = prod.data[0]
    for ts in sect["data"]:
        assert ts > sect["initts"]


def test_201107_mex_negative():
    """Test problem with negative low temperature climo."""
    utcnow = utc(2020, 11, 7)
    prod = mosparser(get_test_file("MOS/MEXAFG.txt"), utcnow=utcnow)
    # Leaked column data
    assert prod.data[0]["data"][utc(2020, 11, 15)]["X_N"] == "7"


@pytest.mark.parametrize("database", ["mos"])
def test_200930_nbx_int(dbcursor):
    """Test a problem found with the product."""
    utcnow = utc(2020, 9, 30, 12)
    prod = mosparser(get_test_file("MOS/NBXUSA_int.txt"), utcnow=utcnow)
    assert len(prod.data) == 6
    inserts = prod.sql(dbcursor)
    assert inserts == 84


@pytest.mark.parametrize("database", ["mos"])
def test_winter_mex(dbcursor):
    """Test that we store the GFSX fields in the winter."""
    utcnow = utc(2020, 9, 1, 0)
    prod = mosparser(get_test_file("MOS/MEXNC1_winter.txt"), utcnow=utcnow)
    assert len(prod.data) == 2
    inserts = prod.sql(dbcursor)
    assert inserts == 30


@pytest.mark.parametrize("database", ["mos"])
def test_nbe(dbcursor):
    """Test that we can parse the NBE."""
    utcnow = utc(2020, 7, 22, 14)
    prod = mosparser(get_test_file("MOS/NBEUSA.txt"), utcnow=utcnow)
    assert len(prod.data) == 2
    inserts = prod.sql(dbcursor)
    assert inserts == 30
    # Check that we parsed data OK
    assert prod.data[0]["data"][utc(2020, 7, 30, 12)]["P12"] == "5"
    assert prod.data[0]["data"][utc(2020, 7, 30, 12)]["PRA"] == "100"


@pytest.mark.parametrize("database", ["mos"])
def test_nbx(dbcursor):
    """Test that we can parse the NBE."""
    utcnow = utc(2020, 7, 22, 14)
    prod = mosparser(get_test_file("MOS/NBXUSA.txt"), utcnow=utcnow)
    assert prod.data[0]["model"] == "NBE"
    assert len(prod.data) == 3
    inserts = prod.sql(dbcursor)
    assert inserts == 18
    # Check that we parsed data OK
    assert prod.data[0]["data"][utc(2020, 8, 2, 12)]["Q12"] == "0"


@pytest.mark.parametrize("database", ["mos"])
def test_mex(dbcursor):
    """Test that we can parse the Extended GFS MEX."""
    utcnow = utc(2020, 7, 10, 12)
    prod = mosparser(get_test_file("MOS/MEXNC1.txt"), utcnow=utcnow)
    assert len(prod.data) == 4
    inserts = prod.sql(dbcursor)
    assert inserts == 60


@pytest.mark.parametrize("database", ["mos"])
def test_lev(dbcursor):
    """Test that we can parse the GFS LAMP (LEV stored as LAV)."""
    utcnow = utc(2020, 7, 13, 12, 30)
    prod = mosparser(get_test_file("MOS/LEVUSA.txt"), utcnow=utcnow)
    assert prod.data[0]["model"] == "LAV"
    assert max(prod.data[0]["data"].keys()) == utc(2020, 7, 15, 2)
    assert len(prod.data) == 3
    inserts = prod.sql(dbcursor)
    assert inserts == 39


@pytest.mark.parametrize("database", ["mos"])
def test_lav(dbcursor):
    """Test that we can parse the GFS LAMP."""
    utcnow = utc(2020, 7, 10, 12, 30)
    prod = mosparser(get_test_file("MOS/LAVUSA.txt"), utcnow=utcnow)
    assert len(prod.data) == 3
    inserts = prod.sql(dbcursor)
    assert inserts == 75


@pytest.mark.parametrize("database", ["mos"])
def test_ecmwf(dbcursor):
    """Test that we can parse the ECMWF MOS."""
    utcnow = utc(2020, 2, 24, 0)
    prod = mosparser(get_test_file("MOS/ECS.txt"), utcnow=utcnow)
    assert len(prod.data) == 3
    inserts = prod.sql(dbcursor)
    assert inserts == 63


@pytest.mark.parametrize("database", ["mos"])
def test_180125_empty(dbcursor):
    """Can we parse a MOS product with empty data"""
    utcnow = utc(2018, 1, 26, 1)
    prod = mosparser(get_test_file("MOS/MET_empty.txt"), utcnow=utcnow)
    assert len(prod.data) == 3
    assert len(prod.data[0]["data"].keys()) == 21

    inserts = prod.sql(dbcursor)
    assert inserts == 42


@pytest.mark.parametrize("database", ["mos"])
def test_parse(dbcursor):
    """MOS type"""
    utcnow = utc(2017, 8, 12, 12)
    prod = mosparser(get_test_file("MOS/METNC1.txt"), utcnow=utcnow)
    assert len(prod.data) == 4
    assert len(prod.data[0]["data"].keys()) == 21

    inserts = prod.sql(dbcursor)
    assert inserts == (4 * 21)


@pytest.mark.parametrize("database", ["mos"])
def test_empty_nbm(dbcursor):
    """Does an empty product trip us up."""
    utcnow = utc(2018, 11, 7, 17)
    prod = mosparser(get_test_file("MOS/NBSUSA_empty.txt"), utcnow=utcnow)
    assert len(prod.data) == 2

    inserts = prod.sql(dbcursor)
    assert inserts == 0


@pytest.mark.parametrize("database", ["mos"])
def test_nbm_v32(dbcursor):
    """Can we parse the NBM v3.2 data."""
    utcnow = utc(2020, 2, 19, 12)
    prod = mosparser(get_test_file("MOS/NBSUSA_32.txt"), utcnow=utcnow)
    assert len(prod.data) == 3
    inserts = prod.sql(dbcursor)
    assert inserts == 69


@pytest.mark.parametrize("database", ["mos"])
def test_nbm_v32_station(dbcursor):
    """Can we parse the NBM v3.2 data."""
    utcnow = utc(2020, 2, 19, 17)
    prod = mosparser(get_test_file("MOS/NBSUSA_32_station.txt"), utcnow=utcnow)
    assert len(prod.data) == 4
    inserts = prod.sql(dbcursor)
    assert inserts == 92


@pytest.mark.parametrize("database", ["mos"])
def test_nbm(dbcursor):
    """Can we parse the NBM data."""
    utcnow = utc(2018, 11, 7, 15)
    prod = mosparser(get_test_file("MOS/NBSUSA.txt"), utcnow=utcnow)
    assert len(prod.data) == 2

    inserts = prod.sql(dbcursor)
    assert inserts == (2 * 21)

    dbcursor.execute(
        """
        SELECT count(*), max(ftime) from t2018
        where model = 'NBS' and station = 'KALM' and runtime = %s
    """,
        (utcnow,),
    )
    row = dbcursor.fetchone()
    assert row[0] == 21
    assert row[1] == utc(2018, 11, 10, 9)
