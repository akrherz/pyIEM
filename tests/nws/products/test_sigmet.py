"""SIGMET"""
# stdlib
from collections import defaultdict

# 3rd Party
import pytest

# this
from pyiem.exceptions import SIGMETException
from pyiem.nws.products.sigmet import parser, compute_esol
from pyiem.util import utc, get_test_file


def mydict():
    """return dict."""
    return dict(lon=-85.50, lat=42.79)


NWSLI_PROVIDER = defaultdict(mydict)


def test_opairs():
    """Test that exception is raised."""
    utcnow = utc(2021, 1, 9, 7, 58)
    with pytest.raises(SIGMETException):
        parser(
            get_test_file("SIGMETS/SIGAK3.txt"),
            utcnow,
            nwsli_provider=NWSLI_PROVIDER,
        )


def test_190503_badgeom():
    """This SIGMET produced a traceback in prod."""
    utcnow = utc(2019, 5, 3, 18, 25)
    tp = parser(
        get_test_file("SIGMETS/SIGC_badgeom.txt"),
        utcnow,
        nwsli_provider=NWSLI_PROVIDER,
    )
    assert len(tp.sigmets) == 4


def test_170815_pywwa_issue3():
    """This example was in pyWWA issues list, so lets test here"""
    utcnow = utc(2015, 9, 30, 16, 56)

    tp = parser(
        get_test_file("SIGMETS/SIGE.txt"),
        utcnow,
        nwsli_provider=NWSLI_PROVIDER,
    )
    assert len(tp.sigmets) == 4


def test_150930_sigak2():
    """Got an error with this product"""
    utcnow = utc(2015, 9, 30, 16, 56)
    tp = parser(get_test_file("SIGMETS/SIGAK2.txt"), utcnow)
    assert not tp.sigmets


def test_150921_sigpas():
    """Got an error with this product"""
    utcnow = utc(2015, 9, 21, 10, 57)
    tp = parser(get_test_file("SIGMETS/SIGPAS.txt"), utcnow)
    assert len(tp.sigmets) == 1


def test_150917_cancel():
    """Don't error out on a CANCELs SIGMET"""
    utcnow = utc(2015, 9, 17, 0, 0)
    tp = parser(get_test_file("SIGMETS/SIGPAP_cancel.txt"), utcnow)
    assert not tp.sigmets


def test_compute_esol():
    """Test our algo on either side of a line"""
    pts = [[0, 0], [5, 0]]
    pts = compute_esol(pts, 111)
    print(pts)
    assert abs(pts[0][0] - 0.00) < 0.01
    assert abs(pts[0][1] - 1.00) < 0.01
    assert abs(pts[1][0] - 5.00) < 0.01
    assert abs(pts[1][1] - 1.00) < 0.01
    assert abs(pts[2][0] - 5.00) < 0.01
    assert abs(pts[2][1] - -1.00) < 0.01
    assert abs(pts[3][0] - 0.00) < 0.01
    assert abs(pts[3][1] - -1.00) < 0.01
    assert abs(pts[4][0] - 0.00) < 0.01
    assert abs(pts[4][1] - 1.00) < 0.01


def test_150915_line():
    """See about parsing a SIGMET LINE"""
    utcnow = utc(2015, 9, 15, 2, 55)
    ugc_provider = {}
    nwsli_provider = {
        "MSP": dict(lon=-83.39, lat=44.45),
        "MCW": dict(lon=-85.50, lat=42.79),
    }
    tp = parser(
        get_test_file("SIGMETS/SIGC_line.txt"),
        utcnow,
        ugc_provider,
        nwsli_provider,
    )
    assert abs(tp.sigmets[0].geom.area - 0.47) < 0.01


def test_150915_isol():
    """See about parsing a SIGMET ISOL"""
    utcnow = utc(2015, 9, 12, 23, 55)
    ugc_provider = {}
    nwsli_provider = {
        "FTI": dict(lon=-83.39, lat=44.45),
        "CME": dict(lon=-85.50, lat=42.79),
    }
    tp = parser(
        get_test_file("SIGMETS/SIGC_ISOL.txt"),
        utcnow,
        ugc_provider,
        nwsli_provider,
    )
    assert abs(tp.sigmets[0].geom.area - 0.30) < 0.01
    assert abs(tp.sigmets[1].geom.area - 0.30) < 0.01


def test_150915_nospace():
    """See about parsing a SIGMET that has no spaces"""
    utcnow = utc(2015, 9, 15, 15, 41)
    tp = parser(get_test_file("SIGMETS/SIGAX.txt"), utcnow)
    assert abs(tp.sigmets[0].geom.area - 23.47) < 0.01


def test_140907_circle():
    """See about parsing a SIGMET that is circle?"""
    utcnow = utc(2014, 9, 6, 22, 15)
    tp = parser(get_test_file("SIGMETS/SIGP0H.txt"), utcnow)
    assert abs(tp.sigmets[0].geom.area - 11.70) < 0.01


def test_140813_line():
    """See about parsing a SIGMET that is a either side of line"""
    utcnow = utc(2014, 8, 12, 13, 15)
    tp = parser(get_test_file("SIGMETS/SIGP0A_line.txt"), utcnow)
    assert abs(tp.sigmets[0].geom.area - 4.32) < 0.01


def test_140815_cancel():
    """See about parsing a SIGMET that is a either side of line"""
    utcnow = utc(2014, 8, 15, 23, 41)
    tp = parser(get_test_file("SIGMETS/SIG_cancel.txt"), utcnow)
    assert not tp.sigmets


def test_sigaoa():
    """SIGAOA"""
    utcnow = utc(2014, 8, 11, 19, 15)
    tp = parser(get_test_file("SIGMETS/SIGA0A.txt"), utcnow)
    assert abs(tp.sigmets[0].geom.area - 24.35) < 0.01


def test_sigaob():
    """See about parsing 50E properly"""
    utcnow = utc(2014, 8, 11, 19, 15)
    tp = parser(get_test_file("SIGMETS/SIGA0B.txt"), utcnow)
    assert not tp.sigmets


@pytest.mark.parametrize("database", ["postgis"])
def test_50e(dbcursor):
    """See about parsing 50E properly"""
    utcnow = utc(2014, 8, 11, 18, 55)
    ugc_provider = {}
    nwsli_provider = {
        "ASP": dict(lon=-83.39, lat=44.45),
        "ECK": dict(lon=-82.72, lat=43.26),
        "GRR": dict(lon=-85.50, lat=42.79),
    }

    tp = parser(
        get_test_file("SIGMETS/SIGE3.txt"),
        utcnow,
        ugc_provider,
        nwsli_provider,
    )
    assert abs(tp.sigmets[0].geom.area - 2.15) < 0.01
    tp.sql(dbcursor)


def test_sigc():
    """See about parsing SIGC"""
    utcnow = utc(2014, 8, 11, 16, 55)
    ugc_provider = {}
    nwsli_provider = {}
    for sid in (
        "MSL,SJI,MLU,LIT,BTR,LEV,LCH,IAH,YQT,SAW,SAT,DYC,AXC,"
        "ODI,DEN,TBE,ADM,JCT,INK,ELP"
    ).split(","):
        nwsli_provider[sid] = dict(lon=-99, lat=45)

    tp = parser(
        get_test_file("SIGMETS/SIGC.txt"), utcnow, ugc_provider, nwsli_provider
    )
    j = tp.get_jabbers("http://localhost", "http://localhost")
    assert tp.sigmets[0].ets == utc(2014, 8, 11, 18, 55)
    ans = "KKCI issues SIGMET 62C for AL MS LA AR till 1855 UTC"
    assert j[0][0] == ans
    ans = (
        "KKCI issues SIGMET 63C for LA TX AND MS LA TX CSTL WTRS till 1855 UTC"
    )
    assert j[1][0] == ans


def test_sigpat():
    """Make sure we don't have another failure with geom parsing"""
    utcnow = utc(2014, 8, 11, 12, 34)
    tp = parser(get_test_file("SIGMETS/SIGPAT.txt"), utcnow)
    j = tp.get_jabbers("http://localhost", "http://localhost")
    assert abs(tp.sigmets[0].geom.area - 33.71) < 0.01
    assert tp.sigmets[0].sts == utc(2014, 8, 11, 12, 35)
    assert tp.sigmets[0].ets == utc(2014, 8, 11, 16, 35)
    assert j[0][0] == "PHFO issues SIGMET TANGO 1 till 1635 UTC"
