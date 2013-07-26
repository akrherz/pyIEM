import unittest
import os

from pyiem.nws.products.mcd import parser as mcdparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestMCD(unittest.TestCase):
    
    def test_simple(self):
        ''' Simple '''
        prod = mcdparser( get_file('SWOMCD.txt') )
        self.assertAlmostEqual(prod.geometry.area, 4.302, 3)
        self.assertEqual(prod.discussion_num, 1525 )
        self.assertEqual(prod.attn_wfo[2], 'DLH')
        self.assertEqual(prod.areas_affected, ("PORTIONS OF NRN WI AND "
                                               +"THE UPPER PENINSULA OF MI"))
