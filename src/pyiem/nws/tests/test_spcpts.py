import unittest
import datetime
import pytz

from pyiem.nws import spcpts
from pyiem.nws import product

class TestObservation(unittest.TestCase):
    
    def test_str1(self):
        """ check spcpts parsing """
        data = open('data/product_examples/SPCPTS.txt').read()
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        self.assertEqual(spc.issue, datetime.datetime(2013, 3, 29, 8, 48, 
                                tzinfo=pytz.timezone("UTC")) )
        self.assertEqual(spc.valid, datetime.datetime(2013, 3, 31, 12, 0, 
                                tzinfo=pytz.timezone("UTC")) )        
        self.assertEqual(spc.expire, datetime.datetime(2013, 4, 1, 12, 0, 
                                tzinfo=pytz.timezone("UTC")) )