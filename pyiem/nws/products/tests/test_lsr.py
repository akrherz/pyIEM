"""Test Local Storm Report parsing."""
import os

from pyiem.nws.products.lsr import parser


def get_file(name):
    """Helper function to get the text file contents."""
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/LSR/%s" % (basedir, name)
    return open(fn, 'rb').read().decode('utf-8')


def test_issue61_future():
    """Can we properly warn on a product from the future."""
    prod = parser(get_file('LSRGSP_future.txt'))
    assert len(prod.warnings) == 1
    assert not prod.lsrs
