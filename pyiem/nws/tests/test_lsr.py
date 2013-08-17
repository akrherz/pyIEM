import unittest

from pyiem.nws.products.lsr import _mylowercase

class TestLSR(unittest.TestCase):
    
    def test_lowercase(self):
        ''' Make sure we can properly convert cities to mixed case '''
        self.assertEqual(_mylowercase("1 N AMES"), "1 N Ames")
        self.assertEqual(_mylowercase("1 NNW AMES"), "1 NNW Ames")
                
