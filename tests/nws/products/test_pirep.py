"""PIREP."""

import pytest
from pyiem.nws.products.pirep import parser as pirepparser
from pyiem.util import utc, get_test_file


def test_210121_int_latlon():
    """Test successful parsing of an integer lat lon value, tricky."""
    utcnow = utc(2020, 1, 21, 10, 22)
    prod = pirepparser(get_test_file("PIREPS/latlonint.txt"), utcnow=utcnow)
    assert prod.reports[0].latitude == 47
    assert prod.reports[0].longitude == -51


def test_210110_canada():
    """Test that generated error is for canada site id."""
    utcnow = utc(2020, 1, 11, 3, 47)
    prod = pirepparser(get_test_file("PIREPS/canada.txt"), utcnow=utcnow)
    assert "CYAT" in prod.warnings[0]


@pytest.mark.parametrize("database", ["postgis"])
def test_210108_emptygeom(dbcursor):
    """Test that we insert empty geometries."""
    utcnow = utc(2020, 1, 1, 21, 34)
    prod = pirepparser(get_test_file("PIREPS/badgeom.txt"), utcnow=utcnow)
    prod.reports[3].is_duplicate = True
    prod.assign_cwsu(dbcursor)
    prod.sql(dbcursor)
    prod.get_jabbers("")
    assert len(prod.reports) == 6
    dbcursor.execute(
        "SELECT count(*) from pireps where valid = %s and "
        "ST_IsEmpty(geom::geometry)",
        (utcnow,),
    )
    assert dbcursor.fetchone()[0] >= 1


@pytest.mark.parametrize("database", ["postgis"])
def test_180307_aviation_controlchar(dbcursor):
    """Darn Aviation control character showing up in WMO products"""
    nwsli_provider = {"BWI": {"lat": 44.26, "lon": -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/ubmd90.txt"), nwsli_provider=nwsli_provider
    )
    assert len(prod.reports) == 1
    prod.assign_cwsu(dbcursor)
    prod.sql(dbcursor)


def test_170324_ampersand():
    """Do we properly escape the ampersand"""
    nwsli_provider = {"DUG": {"lat": 44.26, "lon": -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/ampersand.txt"), nwsli_provider=nwsli_provider
    )
    j = prod.get_jabbers("unused")
    ans = (
        "Routine pilot report at 1259Z: DUG UA /OV SSO/"
        "TM 1259/FL340/TP CRJ9/TB LT TURB &amp; CHOP/RM ZAB FDCS"
    )
    assert j[0][0] == ans
    prod.reports[0].is_duplicate = True
    assert not prod.get_jabbers("")


def test_161010_missingtime():
    """prevent geom parse error"""
    nwsli_provider = {
        "GTF": {"lat": 44.26, "lon": -88.52},
        "ALB": {"lat": 44.26, "lon": -88.52},
    }
    prod = pirepparser(
        get_test_file("PIREPS/PRCUS.txt"),
        nwsli_provider=nwsli_provider,
        utcnow=utc(2016, 10, 1, 1, 35),
    )
    assert prod.reports[0].valid == utc(2016, 9, 30, 19, 25)
    j = prod.get_jabbers("unused")
    assert j[0][2]["channels"] == "UA.None,UA.PIREP"


def test_151210_badgeom():
    """prevent geom parse error"""
    nwsli_provider = {"GCC": {"lat": 44.26, "lon": -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/badgeom.txt"), nwsli_provider=nwsli_provider
    )
    assert prod.reports[0].latitude is None


def test_150202_groupdict():
    """groupdict.txt threw an error"""
    nwsli_provider = {"GCC": {"lat": 44.26, "lon": -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/groupdict.txt"), nwsli_provider=nwsli_provider
    )
    assert len(prod.reports) == 6


def test_150202_airmet():
    """airmet.txt has no valid data, so don't error out"""
    prod = pirepparser(get_test_file("PIREPS/airmet.txt"))
    assert not prod.reports


def test_150126_space():
    """space.txt has a space where it should not"""
    nwsli_provider = {"CZBA": {"lat": 44.26, "lon": -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/space.txt"), nwsli_provider=nwsli_provider
    )
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.132) < 0.01


def test_150121_offset():
    """offset.txt and yet another /OV iteration"""
    nwsli_provider = {
        "MRF": {"lat": 44.26, "lon": -88.52},
        "PDT": {"lat": 44.26, "lon": -88.52},
        "HQZ": {"lat": 44.26, "lon": -88.52},
    }
    prod = pirepparser(
        get_test_file("PIREPS/offset.txt"), nwsli_provider=nwsli_provider
    )
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.510) < 0.01
    assert abs(prod.reports[1].latitude - 44.26) < 0.01
    assert abs(prod.reports[2].latitude - 44.2099) < 0.01


def test_150121_runway():
    """runway.txt has KATW on the runway, this was not good"""
    nwsli_provider = {
        "ATW": {"lat": 44.26, "lon": -88.52},
        "IPT": {"lat": 44.26, "lon": -88.52},
    }
    prod = pirepparser(
        get_test_file("PIREPS/runway.txt"), nwsli_provider=nwsli_provider
    )
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.26) < 0.01
    assert abs(prod.reports[1].longitude - -88.52) < 0.01


def test_150121_fourchar():
    """Another coding edition with four char identifiers"""
    nwsli_provider = {
        "FAR": {"lat": 44, "lon": -99},
        "SMF": {"lat": 42, "lon": -99},
        "RDD": {"lat": 43, "lon": -100},
    }
    prod = pirepparser(
        get_test_file("PIREPS/fourchar.txt"), nwsli_provider=nwsli_provider
    )
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.115) < 0.01
    assert abs(prod.reports[1].latitude - 42.50) < 0.01


def test_150120_latlonloc():
    """latlonloc.txt Turns out there is a LAT/LON option for OV"""
    prod = pirepparser(get_test_file("PIREPS/latlonloc.txt"))
    assert not prod.warnings
    assert prod.reports[0].latitude == 25.00
    assert prod.reports[0].longitude == -70.00
    assert prod.reports[1].latitude == 39.00
    assert prod.reports[1].longitude == -45.00

    prod = pirepparser(get_test_file("PIREPS/latlonloc2.txt"))
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 38.51) < 0.01
    assert abs(prod.reports[0].longitude - -144.3) < 0.01

    nwsli_provider = {"PKTN": {"lat": 44, "lon": -99}}
    prod = pirepparser(
        get_test_file("PIREPS/PKTN.txt"), nwsli_provider=nwsli_provider
    )
    assert not prod.warnings


def test_150120_OVO():
    """PIREPS/OVO.txt has a location of OV 0"""
    nwsli_provider = {
        "AVK": {"lat": 44, "lon": 99},
        "TED": {"lat": 61.17, "lon": -149.99},
    }
    prod = pirepparser(
        get_test_file("PIREPS/OVO.txt"), nwsli_provider=nwsli_provider
    )
    assert not prod.warnings
    assert abs(prod.reports[1].latitude - 61.17) > 0.009
    assert abs(prod.reports[1].longitude - -149.99) > 0.009


def test_offset():
    """Test out our displacement logic"""
    lat = 42.5
    lon = -92.5
    nwsli_provider = {"BIL": {"lat": lat, "lon": lon}}
    p = pirepparser(
        "\001\r\r\n000 \r\r\nUBUS01 KMSC 090000\r\r\n",
        nwsli_provider=nwsli_provider,
    )
    lon2, lat2 = p.compute_loc("BIL", 0, 0)
    assert lon2 == lon
    assert lat2 == lat

    lon2, lat2 = p.compute_loc("BIL", 100, 90)
    assert abs(lon2 - -90.239) < 0.01
    assert lat2 == lat

    lon2, lat2 = p.compute_loc("BIL", 100, 0)
    assert lon2 == lon
    assert abs(lat2 - 44.167) < 0.01


def test_1():
    """PIREP.txt, can we parse it!"""
    utcnow = utc(2015, 1, 9, 0, 0)
    nwsli_provider = {
        "BIL": {"lat": 44, "lon": 99},
        "PIB": {"lat": 44, "lon": 99},
        "LBY": {"lat": 45, "lon": 100},
        "MBO": {"lat": 45, "lon": 100},
        "PUB": {"lat": 46, "lon": 101},
        "HPW": {"lat": 47, "lon": 102},
    }
    prod = pirepparser(
        get_test_file("PIREPS/PIREP.txt"),
        utcnow=utcnow,
        nwsli_provider=nwsli_provider,
    )
    assert not prod.warnings

    j = prod.get_jabbers("unused")
    assert j[0][2]["channels"] == "UA.None,UA.PIREP"
