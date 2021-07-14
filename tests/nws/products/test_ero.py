"""WPC ERO."""

import pytest

# Local
from pyiem.nws.products.ero import parser
from pyiem.util import get_test_file


@pytest.mark.parametrize("database", ["postgis"])
def test_basic(dbcursor):
    """Test that we can walk before we run."""
    # https://www.wpc.ncep.noaa.gov/archives/ero/20210714/94e_2021071401.gif
    data = get_test_file("ERO/PBG94E.txt")
    prod = parser(data)
    prod.sql(dbcursor)
    prod.get_jabbers("")
    # prod.draw_outlooks()
    outlook = prod.get_outlook("CATEGORICAL", "MRGL", 1)
    assert abs(outlook.geometry.area - 188.829) < 0.01
