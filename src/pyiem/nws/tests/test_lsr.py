import unittest
import os

from pyiem.nws.lsr import _mylowercase

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestLSR(unittest.TestCase):
    
    def test_lowercase(self):
        ''' Make sure we can properly convert cities to mixed case '''
        self.assertEqual(_mylowercase("1 N AMES"), "1 N Ames")
        self.assertEqual(_mylowercase("1 NNW AMES"), "1 NNW Ames")
                
