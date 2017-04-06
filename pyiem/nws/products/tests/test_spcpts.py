import unittest
import datetime
import pytz
import os
import psycopg2.extras

from pyiem.nws.products.spcpts import parser, str2multipolygon


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/SPCPTS/%s" % (basedir, name)
    return open(fn).read()


class TestPTS(unittest.TestCase):

    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = psycopg2.connect(database='postgis')
        # Note the usage of RealDictCursor here, as this is what
        # pyiem.twistedpg uses
        self.txn = self.dbconn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def tearDown(self):
        ''' This is called after each test, beware '''
        self.dbconn.rollback()
        self.dbconn.close()

    def test_170404_nogeom(self):
        """nogeom error from a 2002 product"""
        with self.assertRaises(Exception):
            _ = parser(get_file('PTSDY1_2002_nogeom.txt'))

    def test_170404_2002(self):
        """Can we parse something from 2002?"""
        spc = parser(get_file('PTSDY1_2002.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 38.92, 2)

    def test_170329_notimp(self):
        """Exception was raised parsing this guy"""
        spc = parser(get_file('PTSDY2_notimp.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
        self.assertAlmostEqual(outlook.geometry.area, 110.24, 2)

    def test_170215_gh23(self):
        """A marginal for the entire country :/"""
        spc = parser(get_file('PTSDY1_gh23.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
        self.assertAlmostEqual(outlook.geometry.area, 19.63, 2)

    def test_150622_ptsdy1_topo(self):
        """PTSDY1_topo.txt """
        spc = parser(get_file('PTSDY1_topo.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 91.91, 2)

    def test_150622_ptsdy2(self):
        """PTSDY2_invalid.txt """
        with self.assertRaises(Exception):
            _ = parser(get_file('PTSDY2_invalid.txt'))

    def test_150622_ptsdy1(self):
        """PTSDY1_nogeom.txt """
        spc = parser(get_file('PTSDY1_nogeom.txt'))
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 95.88, 2)

    def test_150612_ptsdy1_3(self):
        """We got an error with this, so we shall test"""
        spc = parser(get_file('PTSDY1_3.txt'))
        outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
        self.assertAlmostEqual(outlook.geometry.area, 53.94, 2)

    def test_141022_newcats(self):
        """ Make sure we can parse the new categories """
        spc = parser(get_file('PTSDY1_new.txt'))
        outlook = spc.get_outlook('CATEGORICAL', 'ENH')
        self.assertAlmostEqual(outlook.geometry.area, 13.02, 2)
        outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
        self.assertAlmostEqual(outlook.geometry.area, 47.01, 2)

    def test_140709_nogeoms(self):
        """ Make sure we don't have another failure with geom parsing """
        with self.assertRaises(Exception):
            _ = parser(get_file('PTSDY3_nogeoms.txt'))

    def test_140710_nogeom(self):
        """ Had a failure with no geometries parsed """
        with self.assertRaises(Exception):
            _ = parser(get_file('PTSDY2_nogeom.txt'))

    def test_23jul_failure(self):
        ''' CCW line near Boston '''
        data = """40067377 40567433 41317429 42097381 42357259 42566991"""
        res = str2multipolygon(data)
        self.assertAlmostEqual(res[0].area, 7.98403, 5)

    def test_140707_general(self):
        """ Had a problem with General Thunder, lets test this """
        spc = parser(get_file('PTSDY1_complex.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('CATEGORICAL', 'TSTM')
        self.assertAlmostEqual(outlook.geometry.area, 606.33, 2)

    def test_complex(self):
        ''' Test our processing '''
        spc = parser(get_file('PTSDY3.txt'))
        outlook = spc.get_outlook('ANY SEVERE', '0.05')
        self.assertAlmostEqual(outlook.geometry.area, 10.12, 2)

    def test_bug_140601_pfwf38(self):
        ''' Encounted issue with Fire Outlook Day 3-8 '''
        spc = parser(get_file('PFWF38.txt'))
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 3)

    def test_bug_140507_day1(self):
        ''' Bug found in production with GEOS Topology Exception '''
        spc = parser(get_file('PTSDY1_topoexp.txt'))
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 14)

    def test_bug_140506_day2(self):
        ''' Bug found in production '''
        spc = parser(get_file('PTSDY2.txt'))
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 6)

    def test_bug_140518_day2(self):
        ''' 18 May 2014 tripped error with no exterior polygon found '''
        spc = parser(get_file('PTSDY2_interior.txt'))
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 1)

    def test_bug_140519_day1(self):
        ''' 19 May 2014 tripped error with no exterior polygon found '''
        spc = parser(get_file('PTSDY1_interior.txt'))
        # spc.draw_outlooks()
        self.assertEquals(len(spc.outlooks), 7)

    def test_bug(self):
        ''' Test bug list index outof range '''
        spc = parser(get_file('PTSDY1_2.txt'))
        self.assertEquals(len(spc.outlooks), 1)

    def test_complex_2(self):
        ''' Test our processing '''
        spc = parser(get_file('PTSDY1.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('HAIL', '0.05')
        self.assertAlmostEqual(outlook.geometry.area,  47.65, 2)

    def test_str1(self):
        """ check spcpts parsing """
        spc = parser(get_file('SPCPTS.txt'))
        # spc.draw_outlooks()
        self.assertEqual(spc.valid,
                         datetime.datetime(2013, 7, 19, 19, 52,
                                           tzinfo=pytz.timezone("UTC")))
        self.assertEqual(spc.issue,
                         datetime.datetime(2013, 7, 19, 20, 0,
                                           tzinfo=pytz.timezone("UTC")))
        self.assertEqual(spc.expire,
                         datetime.datetime(2013, 7, 20, 12, 0,
                                           tzinfo=pytz.timezone("UTC")))

        spc.sql(self.txn)
        spc.compute_wfos(self.txn)
        j = spc.get_jabbers("")
        self.assertTrue(len(j) >= 1)
