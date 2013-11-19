import unittest
import datetime
import pytz
import os

from pyiem.nws import spcpts
from pyiem.nws import product

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestObservation(unittest.TestCase):
    
    def test_23jul_failure(self):
        ''' CCW line near Boston '''
        data = """40067377 40567433 41317429 42097381 42357259 42566991"""
        res = spcpts.str2multipolygon(data)
        self.assertAlmostEqual(res[0].area, 7.98403, 5)
        
    def test_pts2polygon(self):
        """ See if we can try points into a polygon! """
        data = """49089764 47719319 46629132 45669060 44729137 44419302
       44349525 44139649 43009650 41989622 41579580 41659434
       43199118 45888811 47308458 99999999 42596895 41607138
       41327230 40057412 39037477 38007549 37467581 36497604
       34227550 99999999 28200045 27869960 27579872 27559822
       27789787 28239780 28589788 29609838 30419863 31599867
       32169873 32999860 34059803 35089742 36079658 36939600
       37369639 37399709 37259792 36809917 36130051 35550161
       35070286 34400381 33260438 32460422 29590238 99999999
       32271635 35851546 36861579 37891713 38761773 39901800
       40501765 40941660 41061555 40901483 40251426 40001391
       40091298 40331239 40841154 41101094 41181008 41440942
       41940912 42600962 43321020 44241040 45301038 45760895
       45790787 45940703 46320669 46740669 47430697 47810736
       48030915 48371232 48521381 48971567 49501688"""
        res = spcpts.str2multipolygon(data)
        self.assertAlmostEqual(res[0].area, 624.10, 2) 
    
    def test_111913(self):
        ''' Test a exception with str2multipolygon '''
        data = get_file('PTSDY3.txt')
        tp = product.TextProduct( data )
        self.assertRaises(Exception, spcpts.SPCPTS, tp )
    
    def test_str1(self):
        """ check spcpts parsing """
        basedir = os.path.dirname(__file__)
        data = get_file('SPCPTS.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        spc.draw_outlooks()
        self.assertEqual(spc.issue, datetime.datetime(2013, 7, 19, 19, 52, 
                                tzinfo=pytz.timezone("UTC")) )
        self.assertEqual(spc.valid, datetime.datetime(2013, 7, 19, 20, 0, 
                                tzinfo=pytz.timezone("UTC")) )        
        self.assertEqual(spc.expire, datetime.datetime(2013, 7, 20, 12, 0, 
                                tzinfo=pytz.timezone("UTC")) )