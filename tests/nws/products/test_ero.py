"""WPC ERO."""

import pytest

# Local
from pyiem.nws.products import parser
from pyiem.util import get_test_file, utc


def test_211025_nullgeom():
    """Trouble spotted in the wild."""
    with pytest.raises(ValueError):
        parser(get_test_file("ERO/RBG94E_nullgeom.txt"))


def test_211024_calif():
    """Test that we get the right geometries."""
    prod = parser(get_test_file("ERO/RBG94E_calif.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "MDT", 1)
    assert abs(outlook.geometry.area - 10.62) < 0.01


@pytest.mark.parametrize("database", ["postgis"])
def test_210817_length(dbcursor):
    """Test our database insert."""
    prod = parser(get_test_file("ERO/RBG94E_dblen.txt"))
    prod.sql(dbcursor)


def test_210716_4f4():
    """Test our updated station table."""
    prod = parser(get_test_file("ERO/RBG94E_4F4.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "MRGL", 1)
    assert abs(outlook.geometry.area - 127.07999) < 0.01


def test_210714_duplicate():
    """Test that we do not have duplicate sfstns entries causing grief."""
    prod = parser(get_test_file("ERO/RBG98E_dup.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "MRGL", 2)
    assert abs(outlook.geometry.area - 96.5306) < 0.01


def test_get_jabbers():
    """Test the wordsmithing and channels emitted."""
    prod = parser(get_test_file("ERO/RBG94E.txt"))
    j = prod.get_jabbers("")
    ans = (
        "The Weather Prediction Center issues Day 1 Excessive Rainfall "
        "Outlook at Jul 13, 21:56z "
        "https://www.wpc.ncep.noaa.gov/archives/web_pages/ero/ero.shtml"
    )
    assert j[-1][0] == ans
    assert "ERODY1" in j[-1][2]["channels"]


def test_timestamps():
    """Test the parsing of timestamps."""
    prod = parser(get_test_file("ERO/RBG94E.txt").replace("12Z ", "1200Z "))
    assert prod.expire == utc(2021, 7, 14, 12)


def test_get_unknown_outlooks():
    """Test that we can handle not finding things."""
    prod = parser(get_test_file("ERO/RBG94E.txt"))
    assert prod.get_outlook("CATEGORICAL", "SLGT", "Q") is None
    assert prod.get_outlook("Q", "SLGT", 1) is None


@pytest.mark.parametrize("database", ["postgis"])
def test_cycle_lifecycle(dbcursor):
    """Test the logic with the cycle lifecycle checks."""
    data = get_test_file("ERO/RBG94E.txt")
    ans = [1, 8, -1, 8, 16, -1]
    rx = ["1000 PM", "400 AM", "359 AM", "401 AM", "1 PM", "0750 PM"]
    for i, r in enumerate(rx):
        prod = parser(data.replace("556 PM", r))
        prod.sql(dbcursor)
        assert prod.cycle == ans[i]


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
