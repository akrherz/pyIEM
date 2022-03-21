"""CWA"""
# third party
import pytest
from shapely.geometry import Polygon

# this
from pyiem.nws.products.cwa import parser
from pyiem.util import utc, get_test_file

LOCS = {
    "AMG": {"lon": -82.51, "lat": 31.54},
    "BNA": {"lon": -86.68, "lat": 36.14},
    "CLT": {"lon": -80.93, "lat": 35.22},
    "HRV": {"lon": -90.00, "lat": 28.85},
    "MCI": {"lon": -94.74, "lat": 39.29},
    "PSK": {"lon": -80.71, "lat": 37.09},
    "SJI": {"lon": -88.36, "lat": 30.73},
    "SZW": {"lon": -84.37, "lat": 30.56},
}


def test_jax():
    """Test that we get something that matched aviationweather.gov"""
    utcnow = utc(2022, 3, 19, 19, 19)
    prod = parser(
        get_test_file("CWA/CWAZJX.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert abs(prod.data.geom.area - 1.5584) < 0.1


@pytest.mark.parametrize("database", ["postgis"])
def test_empty_correction(dbcursor):
    """Test that we get a warning for an empty correction."""
    utcnow = utc(2022, 3, 17, 12, 19)
    prod = parser(
        get_test_file("CWA/CWAZTL_cor.txt").replace(" 102 ", " 1020 "),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    prod.sql(dbcursor)
    assert prod.warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_correction(dbcursor):
    """Test parsing with a correction."""
    utcnow = utc(2022, 3, 17, 12, 19)
    for suffix in ("", "_cor"):
        prod = parser(
            get_test_file(f"CWA/CWAZTL{suffix}.txt"),
            utcnow=utcnow,
            nwsli_provider=LOCS,
        )
        prod.sql(dbcursor)
        prod.get_jabbers("")
        assert not prod.warnings


def test_line():
    """Test handling of a line of given width for a CWA."""
    utcnow = utc(2022, 3, 5, 18)
    prod = parser(
        get_test_file("CWA/CWAZKC_line.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert abs(prod.data.geom.area - 0.1411) < 0.01


@pytest.mark.parametrize("database", ["postgis"])
def test_cancel(dbcursor):
    """Test that we don't get tripped up by CANCEL statements."""
    utcnow = utc(2022, 3, 5, 18)
    prod = parser(
        get_test_file("CWA/CWAZHU_cancel.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    prod.sql(dbcursor)
    prod.get_jabbers("")

    prod = parser(
        get_test_file("CWA/CWAZOA_cancel.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert not prod.warnings


def test_circle():
    """Test that circles can be parsed."""
    utcnow = utc(2022, 3, 7, 20)
    prod = parser(
        get_test_file("CWA/CWAZHU_circle.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert isinstance(prod.data.geom, Polygon)


@pytest.mark.parametrize("database", ["postgis"])
def test_circle2(dbcursor):
    """Test that circles can be parsed."""
    utcnow = utc(2022, 3, 7, 20)
    prod = parser(
        get_test_file("CWA/CWAZHU_circle2.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert isinstance(prod.data.geom, Polygon)
    assert abs(prod.data.geom.area - 0.0098) < 0.01
    prod.sql(dbcursor)


def test_twoline():
    """Test parsing a CWA with two lines of locations."""
    utcnow = utc(2022, 3, 10, 20)
    prod = parser(
        get_test_file("CWA/CWAZAB_twoline.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    jmsgs = prod.get_jabbers("")
    ans = (
        "ZAB issues CWA 101 till 10 Mar 1746Z ... AREA OCNL LIFR CONDS CIG "
        "BLW 005 IN BR . NM TX https://mesonet.agron.iastate.edu/p.php?"
        "pid=202203101546-KZAB-FAUS21-CWAZAB"
    )
    assert jmsgs[0][2]["twitter"] == ans
