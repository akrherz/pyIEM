"""WPC ERO."""

import pytest

# Local
from pyiem.nws.products.ero import parser
from pyiem.util import get_test_file


def test_draw_outlooks():
    """Test that an outlook can be drawn."""
    prod = parser(get_test_file("ERO/RBG99E.txt"))
    prod.draw_outlooks()


def test_day():
    """Test that we get the day right for the various products."""
    for i, num in enumerate([94, 98, 99]):
        prod = parser(get_test_file(f"ERO/RBG{num}E.txt"))
        assert prod.day == i + 1


@pytest.mark.parametrize("database", ["postgis"])
def test_basic(dbcursor):
    """Test that we can walk before we run."""
    # https://www.wpc.ncep.noaa.gov/archives/ero/20210714/94e_2021071401.gif
    data = get_test_file("ERO/RBG94E.txt")
    prod = parser(data)
    prod.sql(dbcursor)
    prod.get_jabbers("")
    # prod.draw_outlooks()
    outlook = prod.get_outlook("CATEGORICAL", "MRGL", 1)
    assert abs(outlook.geometry.area - 188.754) < 0.01
