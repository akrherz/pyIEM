"""Test Local Storm Report parsing."""
# pylint: disable=redefined-outer-name

import pytest
from pyiem.util import get_test_file, get_dbconn
from pyiem.nws.products.lsr import parser


@pytest.fixture
def dbcursor():
    """Database cursor."""
    return get_dbconn("postgis").cursor()


def test_sql(dbcursor):
    """Test that we can insert into the database."""
    prod = parser(get_test_file("LSRBOX.txt"))
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
