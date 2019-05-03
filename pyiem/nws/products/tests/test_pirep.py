"""PIREP."""

from pyiem.nws.products.pirep import parser as pirepparser
from pyiem.util import utc, get_test_file


def test_180307_aviation_controlchar():
    """Darn Aviation control character showing up in WMO products"""
    nwsli_provider = {'BWI': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/ubmd90.txt"), nwsli_provider=nwsli_provider)
    assert len(prod.reports) == 1


def test_170324_ampersand():
    """Do we properly escape the ampersand"""
    nwsli_provider = {'DUG': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/ampersand.txt"), nwsli_provider=nwsli_provider)
    j = prod.get_jabbers()
    ans = (
        "Routine pilot report at 1259Z: DUG UA /OV SSO/"
        "TM 1259/FL340/TP CRJ9/TB LT TURB &amp; CHOP/RM ZAB FDCS"
    )
    assert j[0][0] == ans


def test_161010_missingtime():
    """prevent geom parse error"""
    nwsli_provider = {
        'GTF': {'lat': 44.26, 'lon': -88.52},
        'ALB': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/PRCUS.txt"), nwsli_provider=nwsli_provider)
    j = prod.get_jabbers()
    assert j[0][2]['channels'] == 'UA.None,UA.PIREP'


def test_151210_badgeom():
    """prevent geom parse error"""
    nwsli_provider = {'GCC': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/badgeom.txt"), nwsli_provider=nwsli_provider)
    assert not prod.reports


def test_150202_groupdict():
    """groupdict.txt threw an error"""
    nwsli_provider = {'GCC': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file("PIREPS/groupdict.txt"), nwsli_provider=nwsli_provider)
    assert len(prod.reports) == 1


def test_150202_airmet():
    """airmet.txt has no valid data, so don't error out """
    prod = pirepparser(get_test_file('PIREPS/airmet.txt'))
    assert not prod.reports


def test_150126_space():
    """ space.txt has a space where it should not """
    nwsli_provider = {'CZBA': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file('PIREPS/space.txt'), nwsli_provider=nwsli_provider)
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.15) < 0.01


def test_150121_offset():
    """ offset.txt and yet another /OV iteration """
    nwsli_provider = {
        'MRF': {'lat': 44.26, 'lon': -88.52},
        'PDT': {'lat': 44.26, 'lon': -88.52},
        'HQZ': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file('PIREPS/offset.txt'), nwsli_provider=nwsli_provider)
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.48) < 0.01
    assert abs(prod.reports[1].latitude - 44.26) < 0.01
    assert abs(prod.reports[2].latitude - 44.22) < 0.01


def test_150121_runway():
    """ runway.txt has KATW on the runway, this was not good """
    nwsli_provider = {
        'ATW': {'lat': 44.26, 'lon': -88.52},
        'IPT': {'lat': 44.26, 'lon': -88.52}}
    prod = pirepparser(
        get_test_file('PIREPS/runway.txt'), nwsli_provider=nwsli_provider)
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.26) < 0.01
    assert abs(prod.reports[1].longitude - -88.52) < 0.01


def test_150121_fourchar():
    """ Another coding edition with four char identifiers """
    nwsli_provider = {
        'FAR': {'lat': 44, 'lon': -99},
        'SMF': {'lat': 42, 'lon': -99},
        'RDD': {'lat': 43, 'lon': -100}}
    prod = pirepparser(get_test_file('PIREPS/fourchar.txt'),
                       nwsli_provider=nwsli_provider)
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 44.10) < 0.01
    assert abs(prod.reports[1].latitude - 42.50) < 0.01


def test_150120_latlonloc():
    """ latlonloc.txt Turns out there is a LAT/LON option for OV """
    prod = pirepparser(get_test_file('PIREPS/latlonloc.txt'))
    assert not prod.warnings
    assert prod.reports[0].latitude == 25.00
    assert prod.reports[0].longitude == -70.00
    assert prod.reports[1].latitude == 39.00
    assert prod.reports[1].longitude == -45.00

    prod = pirepparser(get_test_file('PIREPS/latlonloc2.txt'))
    assert not prod.warnings
    assert abs(prod.reports[0].latitude - 38.51) < 0.01
    assert abs(prod.reports[0].longitude - -144.3) < 0.01

    nwsli_provider = {'PKTN': {'lat': 44, 'lon': -99}}
    prod = pirepparser(
        get_test_file('PIREPS/PKTN.txt'), nwsli_provider=nwsli_provider)
    assert not prod.warnings


def test_150120_OVO():
    """ PIREPS/OVO.txt has a location of OV 0 """
    nwsli_provider = {'AVK': {'lat': 44, 'lon': 99}}
    prod = pirepparser(
        get_test_file('PIREPS/OVO.txt'), nwsli_provider=nwsli_provider)
    assert not prod.warnings


def test_offset():
    """ Test out our displacement logic """
    lat = 42.5
    lon = -92.5
    nwsli_provider = {'BIL': {'lat': lat, 'lon': lon}}
    p = pirepparser("\001\r\r\n000 \r\r\nUBUS01 KMSC 090000\r\r\n",
                    nwsli_provider=nwsli_provider)
    lon2, lat2 = p.compute_loc("BIL", 0, 0)
    assert lon2 == lon
    assert lat2 == lat

    lon2, lat2 = p.compute_loc("BIL", 100, 90)
    assert abs(lon2 - -90.54) < 0.01
    assert lat2 == lat

    lon2, lat2 = p.compute_loc("BIL", 100, 0)
    assert lon2 == lon
    assert abs(lat2 - 43.95) < 0.01


def test_1():
    """ PIREP.txt, can we parse it! """
    utcnow = utc(2015, 1, 9, 0, 0)
    nwsli_provider = {
        'BIL': {'lat': 44, 'lon': 99},
        'LBY': {'lat': 45, 'lon': 100},
        'PUB': {'lat': 46, 'lon': 101},
        'HPW': {'lat': 47, 'lon': 102}}
    prod = pirepparser(
        get_test_file('PIREPS/PIREP.txt'), utcnow=utcnow,
        nwsli_provider=nwsli_provider)
    assert not prod.warnings

    j = prod.get_jabbers()
    assert j[0][2]['channels'] == 'UA.None,UA.PIREP'
