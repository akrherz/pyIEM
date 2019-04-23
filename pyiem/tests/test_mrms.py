"""tests"""
import datetime
import os
import pytz

from pyiem import mrms


def test_fetch():
    """Can we fetch MRMS files?  Yes we can!"""
    product = 'PrecipRate'
    valid = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
    valid -= datetime.timedelta(minutes=(valid.minute % 2))
    fn = mrms.fetch(product, valid, tmpdir="/tmp")
    if os.path.isfile(fn):
        os.unlink(fn)
    valid = valid.replace(tzinfo=pytz.utc) - datetime.timedelta(minutes=2)
    fn = mrms.fetch(product, valid, tmpdir="/tmp")
    if os.path.isfile(fn):
        os.unlink(fn)
    # we don't actually test anything as the above may not be deterministic


def test_colorramp():
    """See what we can do with a colorramp"""
    cmap = mrms.make_colorramp()
    assert len(cmap) == 256 * 3


def test_write_worldfile():
    """see if we can write a world file"""
    mrms.write_worldfile('/tmp/bah.wld')
    assert os.path.isfile("/tmp/bah.wld")


def test_get_fn():
    """ Test filename func """
    ts = datetime.datetime(2000, 1, 1, 12, 35)
    fn = mrms.get_fn('p24h', ts, 3)
    expected = ("/mnt/a4/data/2000/01/01/mrms/tile3/p24h/"
                "p24h.20000101.123500.gz")
    assert fn == expected


def test_reader():
    """Can we read the legacy file """
    fn = ("%s/../../data/product_examples/1hrad.20130920.190000.gz") % (
        os.path.dirname(__file__), )
    metadata, _ = mrms.reader(fn)
    assert abs(metadata['ul_lat'] - 54.99) < 0.01
