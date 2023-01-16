"""GAIRMET"""

# Third Party
import defusedxml.ElementTree as ET
import mock
import pytest

# Local
from pyiem.nws.products.gairmet import parser, process_airmet
from pyiem.util import get_test_file, utc


def test_220707_freezing():
    """Test a failure in prod."""
    prod = mock.Mock()
    prod.data.freezing_levels = []
    airmet = ET.fromstring(get_test_file("GAIRMET/freezing.xml"))
    process_airmet(prod, airmet)
    assert prod.data.airmets


def test_220701_gmtice():
    """Test a failure in prod."""
    prod = mock.Mock()
    airmet = ET.fromstring(get_test_file("GAIRMET/airmet.xml"))
    process_airmet(prod, airmet)
    assert prod.data.airmets


@pytest.mark.parametrize("database", ["postgis"])
def test_parsing(dbcursor):
    """Test simple parsing."""
    utcnow = utc(2022, 3, 17, 17, 0)
    prod = parser(get_test_file("GAIRMET/LWGE86.txt"), utcnow=utcnow)
    assert len(prod.data.airmets) == 42
    prod.sql(dbcursor)


def test_surface():
    """Test that we get the right surface winds phenomena."""
    utcnow = utc(2022, 3, 17, 17, 0)
    prod = parser(get_test_file("GAIRMET/LWHE00.txt"), utcnow=utcnow)
    assert len(prod.data.airmets) == 52
    ans = "Surface Wind Speed Greater Than 30"
    assert prod.data.airmets[38].weather_conditions[0] == ans
    ans = "Turbulence MODERATE from 0 to 9000"
    assert prod.data.airmets[32].weather_conditions[0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_ice(dbcursor):
    """Test the parsing of Ice information."""
    utcnow = utc(2022, 3, 17, 17, 0)
    prod = parser(get_test_file("GAIRMET/LWIE00.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    assert len(prod.data.airmets) == 20
    assert len(prod.data.freezing_levels) == 30


def test_exception():
    """Test that we handle an exception cleanly."""
    utcnow = utc(2022, 3, 17, 17, 0)
    data = (
        get_test_file("GAIRMET/LWGE86.txt")
        .replace("2022-03-17T21:00:00Z", "2022-03-17TZZ:00:00")
        .replace("true", "false")
    )
    prod = parser(data, utcnow=utcnow)
    assert prod.warnings
    with pytest.raises(Exception):
        parser(data.replace("G-AIRMET", "BOOO"), utcnow=utcnow)
