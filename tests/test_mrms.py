"""tests"""
import datetime
import os

from pyiem import mrms
from pyiem.util import utc

PRODUCT = "PrecipRate"
CENTERS = ["mtarchive", "bldr", "cprk"]


def test_fetch_failback(requests_mock):
    """Can we get files that we don't have."""
    # A file from the future suffices
    valid = utc() + datetime.timedelta(hours=1)
    for center in CENTERS:
        requests_mock.get(
            mrms.get_url(center, valid, PRODUCT), status_code=404
        )
    fn = mrms.fetch(PRODUCT, valid, tmpdir="/tmp")
    assert fn is None


def test_fetch(requests_mock):
    """Can we fetch MRMS files?  Yes we can!"""
    valid = utc()
    requests_mock.get(
        mrms.get_url("mtarchive", valid, PRODUCT), content=b"\x1f\x8bHello"
    )
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


def test_get_fn():
    """ Test filename func """
    ts = datetime.datetime(2000, 1, 1, 12, 35)
    fn = mrms.get_fn("p24h", ts, 3)
    expected = (
        "/mnt/a4/data/2000/01/01/mrms/tile3/p24h/p24h.20000101.123500.gz"
    )
    assert fn == expected


def test_reader():
    """Can we read the legacy file """
    fn = ("%s/../data/product_examples/1hrad.20130920.190000.gz") % (
        os.path.dirname(__file__),
    )
    metadata, _ = mrms.reader(fn)
    assert abs(metadata["ul_lat"] - 54.99) < 0.01
