"""tests"""

import datetime
import os

import httpx
import pytest
from pytest_httpx import HTTPXMock

from pyiem import mrms
from pyiem.util import utc

PRODUCT = "PrecipRate"
CENTERS = ["mtarchive", "", "bldr", "cprk"]


def test_find_ij():
    """Test the find_ij function."""
    i, j = mrms.find_ij(-42.0, 95.0)
    assert i is None
    assert j is None
    i, j = mrms.find_ij(
        mrms.MRMS4IEMRE_WEST_EDGE + 0.0001, mrms.MRMS4IEMRE_SOUTH_EDGE + 0.0001
    )
    assert i == 0
    assert j == 0


def test_2001_mrms():
    """Test that we can fetch older MRMS data in a bit different location."""
    # NB archive starts at 12z on the 1rst day of 2001
    fn = mrms.fetch("PrecipRate", utc(2001, 1, 2), tmpdir="/tmp")
    assert fn is not None


def test_nofailback(httpx_mock: HTTPXMock):
    """Test that code bails on old date."""
    httpx_mock.add_response(status_code=404)
    valid = utc() - datetime.timedelta(days=20)
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is None


def test_failback(httpx_mock: HTTPXMock):
    """Test that we can do option 3."""
    httpx_mock.add_response(status_code=404)
    httpx_mock.add_response(content=b"\x1f\x8bHello")
    valid = utc() + datetime.timedelta(hours=1)
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is not None
    os.unlink(fn)


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_exception(httpx_mock: HTTPXMock):
    """Test what happens when we raise an exception."""
    httpx_mock.add_exception(httpx.TimeoutException)
    valid = utc() + datetime.timedelta(hours=1)
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is None


def test_existing_file():
    """Test that we return once we already have the file on disk."""
    valid = utc()
    fn = f"{PRODUCT}_00.00_{valid:%Y%m%d-%H%M}00.grib2.gz"
    with open(f"/tmp/{fn}", "w", encoding="utf8") as fh:
        fh.write("Hello")
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is not None
    os.unlink(fn)


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_fetch_failback(httpx_mock: HTTPXMock):
    """Can we get files that we don't have."""
    httpx_mock.add_response(status_code=404)
    # A file from the future suffices
    valid = utc() + datetime.timedelta(hours=1)
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is None


def test_fetch(httpx_mock: HTTPXMock):
    """Can we fetch MRMS files?  Yes we can!"""
    httpx_mock.add_response(content=b"\x1f\x8bHello")
    valid = utc()
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is not None
    with open(fn, "rb") as fh:
        assert fh.read() == b"\x1f\x8bHello"
    os.unlink(fn)


def test_colorramp():
    """See what we can do with a colorramp"""
    cmap = mrms.make_colorramp()
    assert len(cmap) == 256 * 3


def test_write_worldfile():
    """see if we can write a world file"""
    mrms.write_worldfile("/tmp/bah.wld")
    assert os.path.isfile("/tmp/bah.wld")


def test_reader():
    """Can we read the legacy file"""
    fn = (
        f"{os.path.dirname(__file__)}/../data/product_examples/"
        "1hrad.20130920.190000.gz"
    )
    metadata, _ = mrms.reader(fn)
    assert abs(metadata["ul_lat"] - 54.99) < 0.01
