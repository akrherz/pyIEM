"""Test NLDN."""
import os

from pyiem.nws.products.nldn import parser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/NLDN/%s" % (basedir, name)
    return open(fn, 'rb')


def test_1_basic():
    """CLIBNA is a new diction"""
    np = parser(get_file('example.bin'))
    assert len(np.df.index) == 50
