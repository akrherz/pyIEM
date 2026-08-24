"""tests"""

import datetime
import os
import re

import responses

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


def test_2001_mrms(tmpdir):
    """Test that we can fetch older MRMS data in a bit different location."""
    # NB archive starts at 12z on the 1rst day of 2001
    fn = mrms.fetch("PrecipRate", utc(2001, 1, 2), tmpdir=tmpdir)
    assert fn is not None


@responses.activate
def test_gzipped_dl_from_ncep(tmpdir):
    """Test that we can gunzip something when fetched from NCEP."""
    responses.add(
        responses.GET,
        re.compile(r"https://mtarchive\.geol\.iastate\.edu/.*"),
        status=404,
    )
    # Allow anything ncep to go through unharmed
    for center in ["", "-bldr", "-cprk"]:
        responses.add_passthru(
            re.compile(f"https://mrms{center}.ncep.noaa.gov/2D/.*")
        )
    # This should exist unstream
    valid = (utc() - datetime.timedelta(hours=2)).replace(minute=0)
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
    assert fn is not None


@responses.activate
def test_nofailback(tmpdir):
    """Test that code bails on old date."""
    responses.add(
        responses.GET,
        re.compile(r"https://mtarchive\.geol\.iastate\.edu/.*"),
        status=404,
    )
    valid = utc() - datetime.timedelta(days=20)
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
    assert fn is None


def test_failback(tmpdir):
    """Test that we can do option 3."""
    valid = utc() + datetime.timedelta(hours=1)
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
    assert fn is None


@responses.activate
def test_exception(tmpdir):
    """Test what happens when we raise an exception."""
    responses.add(
        responses.GET,
        re.compile(r"https://mtarchive\.geol\.iastate\.edu/.*"),
        body=responses.ConnectionError("Timeout"),
    )
    valid = utc() + datetime.timedelta(hours=1)
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
    assert fn is None


def test_existing_file(tmpdir):
    """Test that we return once we already have the file on disk."""
    valid = utc()
    fn = f"{PRODUCT}_00.00_{valid:%Y%m%d-%H%M}00.grib2.gz"
    with open(f"{tmpdir}/{fn}", "w", encoding="utf8") as fh:
        fh.write("Hello")
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
    assert fn is not None
    os.unlink(fn)


@responses.activate
def test_failback_fetch(tmpdir):
    """Can we get files that we don't have."""
    responses.add(responses.GET, "http://mtarchive", status=404)
    # A file from the future suffices
    valid = utc() + datetime.timedelta(hours=1)
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
    assert fn is None


@responses.activate
def test_fetch(tmpdir):
    """Can we fetch MRMS files?  Yes we can!"""
    responses.add(
        responses.GET,
        re.compile(r"https://mtarchive\.geol\.iastate\.edu/.*"),
        body=b"\x1f\x8bHello",
    )
    valid = utc()
    fn = mrms.fetch(PRODUCT, valid, tmpdir=tmpdir)
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
