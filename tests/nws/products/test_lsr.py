"""Test Local Storm Report parsing."""
# pylint: disable=redefined-outer-name

import pytest
from pyiem.util import get_test_file, get_dbconn
from pyiem.nws.products.lsr import parser


@pytest.fixture
def dbcursor():
    """Database cursor."""
    return get_dbconn("postgis").cursor()


def test_issue277_oldlsr():
    """Test the tweet generated from a delayed LSR."""
    prod = parser(get_test_file("LSR/LSRDVN_old.txt"))
    assert len(prod.lsrs) == 1
    j = prod.get_jabbers("")
    ans = (
        "[Delayed Report] On Aug 10, at 12:28 PM CDT, 3 WSW Cedar Rapids "
        "[Linn Co, IA] PUBLIC reports "
        "TSTM WND GST of E130 MPH. ROOF REMOVED FROM SMALL "
        "STRIP MALL. SOME EXTERIOR WALLS COLLAPSED. "
        "#DVN/202008101728/202008101728"
    )
    assert j[0][2]["twitter"] == ans


def test_sql(dbcursor):
    """Test that we can insert into the database."""
    prod = parser(get_test_file("LSR/LSRBOX.txt"))
    for lsr in prod.lsrs:
        lsr.sql(dbcursor)


def test_issue170_nan():
    """How are we handling LSRs that have bad NAN magnitudes."""
    prod = parser(get_test_file("LSR/LSRJAN_NAN.txt"))
    assert len(prod.warnings) == 1
    assert not prod.lsrs


def test_issue61_future():
    """Can we properly warn on a product from the future."""
    prod = parser(get_test_file("LSR/LSRGSP_future.txt"))
    assert len(prod.warnings) == 1
    assert not prod.lsrs
