import os
import unittest
from pyiem.nws.products.nldn import parser as parser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/NLDN/%s" % (basedir, name)
    return open(fn)


class TestProducts(unittest.TestCase):
    """ Tests """
    def test_1_basic(self):
        """CLIBNA is a new diction"""
        np = parser(get_file('example.bin'))
        self.assertEquals(len(np.df.index), 50)
