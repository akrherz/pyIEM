import unittest
import datetime
import pytz
import os

from pyiem.nws import spcpts
from pyiem.nws import product


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/SPCPTS/%s" % (basedir, name)
    return open(fn).read()


class TestPTS(unittest.TestCase):

    def test_170215_gh23(self):
        """A marginal for the entire country :/"""
        tp = product.TextProduct(get_file('PTSDY1_gh23.txt'))
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
        self.assertAlmostEqual(outlook.geometry.area, 19.63, 2)

    def test_150622_ptsdy1_topo(self):
        """PTSDY1_topo.txt """
        tp = product.TextProduct(get_file('PTSDY1_topo.txt'))
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 91.91, 2)

    def test_150622_ptsdy2(self):
        """PTSDY2_invalid.txt """
        tp = product.TextProduct(get_file('PTSDY2_invalid.txt'))
        with self.assertRaises(Exception):
            spcpts.SPCPTS(tp)

    def test_150622_ptsdy1(self):
        """PTSDY1_nogeom.txt """
        tp = product.TextProduct(get_file('PTSDY1_nogeom.txt'))
        spc = spcpts.SPCPTS(tp)
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 95.88, 2)

    def test_150612_ptsdy1_3(self):
        """We got an error with this, so we shall test"""
        tp = product.TextProduct(get_file('PTSDY1_3.txt'))
        spc = spcpts.SPCPTS(tp)
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 53.94, 2)

    def test_141022_newcats(self):
        """ Make sure we can parse the new categories """
        tp = product.TextProduct(get_file('PTSDY1_new.txt'))
        spc = spcpts.SPCPTS(tp)
        outlook = spc.get_outlook('CATEGORICAL', 'ENH')
        self.assertAlmostEqual(outlook.geometry.area, 13.02, 2)
        outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
        self.assertAlmostEqual(outlook.geometry.area, 47.01, 2)

    def test_140709_nogeoms(self):
        """ Make sure we don't have another failure with geom parsing """
        tp = product.TextProduct(get_file('PTSDY3_nogeoms.txt'))
        self.assertRaises(Exception, spcpts.SPCPTS, tp)

    def test_140710_nogeom(self):
        """ Had a failure with no geometries parsed """
        tp = product.TextProduct(get_file('PTSDY2_nogeom.txt'))
        self.assertRaises(Exception, spcpts.SPCPTS, tp)
        # spc.draw_outlooks()

    def test_23jul_failure(self):
        ''' CCW line near Boston '''
        data = """40067377 40567433 41317429 42097381 42357259 42566991"""
        res = spcpts.str2multipolygon(data)
        self.assertAlmostEqual(res[0].area, 7.98403, 5)

    def test_140707_general(self):
        """ Had a problem with General Thunder, lets test this """
        data = get_file('PTSDY1_complex.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'TSTM')
        self.assertAlmostEqual(outlook.geometry.area, 606.33, 2)

    def test_complex(self):
        ''' Test our processing '''
        data = get_file('PTSDY3.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        outlook = spc.get_outlook('ANY SEVERE', '0.05')
        self.assertAlmostEqual(outlook.geometry.area, 10.12, 2)

    def test_bug_140601_pfwf38(self):
        ''' Encounted issue with Fire Outlook Day 3-8 '''
        data = get_file('PFWF38.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 3)

    def test_bug_140507_day1(self):
        ''' Bug found in production with GEOS Topology Exception '''
        data = get_file('PTSDY1_topoexp.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 14)

    def test_bug_140506_day2(self):
        ''' Bug found in production '''
        data = get_file('PTSDY2.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 6)

    def test_bug_140518_day2(self):
        ''' 18 May 2014 tripped error with no exterior polygon found '''
        data = get_file('PTSDY2_interior.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 1)

    def test_bug_140519_day1(self):
        ''' 19 May 2014 tripped error with no exterior polygon found '''
        data = get_file('PTSDY1_interior.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 7)

    def test_bug(self):
        ''' Test bug list index outof range '''
        data = get_file('PTSDY1_2.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        self.assertEquals(len(spc.outlooks), 1)

    def test_complex_2(self):
        ''' Test our processing '''
        data = get_file('PTSDY1.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        outlook = spc.get_outlook('HAIL', '0.05')
        self.assertAlmostEqual(outlook.geometry.area,  47.65, 2)

    def test_str1(self):
        """ check spcpts parsing """
        data = get_file('SPCPTS.txt')
        tp = product.TextProduct(data)
        spc = spcpts.SPCPTS(tp)
        # spc.draw_outlooks()
        self.assertEqual(spc.issue,
                         datetime.datetime(2013, 7, 19, 19, 52,
                                           tzinfo=pytz.timezone("UTC")))
        self.assertEqual(spc.valid,
                         datetime.datetime(2013, 7, 19, 20, 0,
                                           tzinfo=pytz.timezone("UTC")))
        self.assertEqual(spc.expire,
                         datetime.datetime(2013, 7, 20, 12, 0,
                                           tzinfo=pytz.timezone("UTC")))
