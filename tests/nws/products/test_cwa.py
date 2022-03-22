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
    "CDV": {"lon": -145.40, "lat": 60.35},
    "CLT": {"lon": -80.93, "lat": 35.22},
    "HRV": {"lon": -90.00, "lat": 28.85},
    "IAH": {"lon": -95.35, "lat": 29.96},
    "LCH": {"lon": -93.11, "lat": 30.14},
    "MCI": {"lon": -94.74, "lat": 39.29},
    "PSK": {"lon": -80.71, "lat": 37.09},
    "RSK": {"lon": -108.10, "lat": 36.75},
    "SJI": {"lon": -88.36, "lat": 30.73},
    "SJN": {"lon": -109.14, "lat": 34.42},
    "SZW": {"lon": -84.37, "lat": 30.56},
    "YAK": {"lon": -139.67, "lat": 59.50},
}


def test_220322_ffrom():
    """Test a seemingly common typo."""
    utcnow = utc(2022, 1, 20)
    prod = parser(
        get_test_file("CWA/CWAZTL.txt").replace("FROM ", "FFROM "),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert not prod.warnings


def test_220322_fourpt_line():
    """Test that a line longer than two points can be made into a polygon."""
    utcnow = utc(2022, 1, 20)
    prod = parser(
        get_test_file("CWA/CWAZHU_line.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert abs(prod.data.geom.area - 1.2695) < 0.001


def test_220322_cancels():
    """Test that we gracefully handle a product that is in tough shape."""
    utcnow = utc(2022, 1, 20)
    prod = parser(
        get_test_file("CWA/CWAZHU_cancel2.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert prod.data is None


def test_theoretical():
    """Test something that I suspect could happen."""
    utcnow = utc(2022, 3, 22)
    data = get_test_file("CWA/CWAZAN_line.txt").replace("CDV", "aaa")
    prod = parser(data, utcnow=utcnow, nwsli_provider=LOCS)
    assert prod.warnings and prod.data is None


def test_220321_zan():
    """Test parsing problematic CWA"""
    utcnow = utc(2022, 3, 22)
    prod = parser(
        get_test_file("CWA/CWAZAN_line.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    ans = (
        "50NM WIDE...AREA LLWS +/- 10-15 KT. RPRT BY ACFT. "
        "CONDS CONTG BYD 220155Z. AK. PTK MAR 2022 CWSU"
    )
    assert prod.data.narrative == ans


def test_220321_badlocation():
    """Test handling of quasi-invalid location details :/"""
    utcnow = utc(2022, 3, 22)
    prod = parser(
        get_test_file("CWA/CWAZAB_bad.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    ans = (
        "AREA OCNL IFR CONDS 30NM WIDE. VIS AS LOW AS 2.5SM IN HZ DU. "
        "VISIBLE ON SATELLITE. CONDS IMPRV AFT 22/0300Z. NM"
    )
    assert prod.data.narrative == ans


def test_jax():
    """Test that we get something that matched aviationweather.gov"""
    utcnow = utc(2022, 3, 19, 19, 19)
    prod = parser(
        get_test_file("CWA/CWAZJX.txt"),
        utcnow=utcnow,
        nwsli_provider=LOCS,
    )
    assert abs(prod.data.geom.area - 1.882) < 0.01


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
    assert abs(prod.data.geom.area - 0.4841) < 0.01


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
    assert abs(prod.data.geom.area - 0.0873) < 0.01
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
