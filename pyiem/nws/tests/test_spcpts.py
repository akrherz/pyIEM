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
    
    def test_140707_general(self):
        """ Had a problem with General Thunder, lets test this """
        data = get_file('PTSDY1_complex.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        #spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'TSTM')
        self.assertAlmostEqual(outlook.geometry.area, 606.33 , 2)
    
    def test_complex(self):
        ''' Test our processing '''
        data = get_file('PTSDY3.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        outlook = spc.get_outlook('ANY SEVERE', '0.05')
        self.assertAlmostEqual(outlook.geometry.area, 10.12 , 2)
    
    def test_bug_140601_pfwf38(self):
        ''' Encounted issue with Fire Outlook Day 3-8 '''
        data = get_file('PFWF38.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS(tp)
        #spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 3 )        
    
    def test_bug_140507_day1(self):
        ''' Bug found in production with GEOS Topology Exception '''
        data = get_file('PTSDY1_topoexp.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS(tp)
        #spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 14 )
    
    def test_bug_140506_day2(self):
        ''' Bug found in production '''
        data = get_file('PTSDY2.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS(tp)
        #spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 6 )
    
    def test_bug_140518_day2(self):
        ''' 18 May 2014 tripped error with no exterior polygon found '''
        data = get_file('PTSDY2_interior.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS(tp)
        #spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 1 )
 
    def test_bug_140519_day1(self):
        ''' 19 May 2014 tripped error with no exterior polygon found '''
        data = get_file('PTSDY1_interior.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS(tp)
        #spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 7 )
    
    def test_bug(self):
        ''' Test bug list index outof range '''
        data = get_file('PTSDY1_2.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        self.assertEquals( len(spc.outlooks), 1)
    
    def test_complex_2(self):
        ''' Test our processing '''
        data = get_file('PTSDY1.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        #spc.draw_outlooks()
        outlook = spc.get_outlook('HAIL', '0.05')
        self.assertAlmostEqual(outlook.geometry.area,  47.65, 2 )
    
    def test_str1(self):
        """ check spcpts parsing """
        data = get_file('SPCPTS.txt')
        tp = product.TextProduct( data )
        spc = spcpts.SPCPTS( tp )
        #spc.draw_outlooks()
        self.assertEqual(spc.issue, datetime.datetime(2013, 7, 19, 19, 52, 
                                tzinfo=pytz.timezone("UTC")) )
        self.assertEqual(spc.valid, datetime.datetime(2013, 7, 19, 20, 0, 
                                tzinfo=pytz.timezone("UTC")) )        
        self.assertEqual(spc.expire, datetime.datetime(2013, 7, 20, 12, 0, 
                                tzinfo=pytz.timezone("UTC")) )