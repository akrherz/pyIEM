"""Unit Tests"""
import unittest
import os

import datetime
import pytz
import psycopg2.extras

from pyiem.nws.products.spcpts import parser, str2multipolygon


def utc(year, month, day, hour, minute):
    """Helper"""
    dt = datetime.datetime(year, month, day, hour, minute)
    return dt.replace(tzinfo=pytz.utc)


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/SPCPTS/%s" % (basedir, name)
    return open(fn).read()


class TestPTS(unittest.TestCase):
    """Run Tests"""

    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = psycopg2.connect(database='postgis', host='iemdb')
        # Note the usage of RealDictCursor here, as this is what
        # pyiem.twistedpg uses
        self.txn = self.dbconn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def tearDown(self):
        ''' This is called after each test, beware '''
        self.dbconn.rollback()
        self.dbconn.close()

    def test_170703_badday3link(self):
        """Day3 URL is wrong"""
        spc = parser(get_file('PTSDY3.txt'))
        jdict = spc.get_jabbers('', '')
        self.assertEquals(jdict[0][0],
                          ('The Storm Prediction Center issues Day 3 '
                           'Convective Outlook at Nov 19, 8:31z '
                           'http://www.spc.noaa.gov/products/outlook/'
                           'archive/2013/day3otlk_20131119_0830.html'))

    def test_170612_nullgeom(self):
        """See why this has an error with null geom reported"""
        spc = parser(get_file('PTSD48_nullgeom.txt'))
        # spc.draw_outlooks()
        spc.sql(self.txn)
        outlook = spc.get_outlook('ANY SEVERE', '0.15', 4)
        self.assertAlmostEqual(outlook.geometry.area, 56.84, 2)

    def test_170522_nogeom(self):
        """See why this has an error with no-geom reported"""
        spc = parser(get_file('PTSDY1_nogeom2.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('TORNADO', '0.02', 1)
        self.assertAlmostEqual(outlook.geometry.area, 2.90, 2)

    def test_170518_bad_dbtime(self):
        """This went into the database with an incorrect expiration time"""
        spc = parser(get_file('PTSDY1_baddbtime.txt'))
        answer = utc(2017, 5, 1, 12, 0)
        for _, outlook in spc.outlook_collections.iteritems():
            self.assertEqual(outlook.expire, answer)

    def test_170428_large(self):
        """PTSDY1 has a large 10 tor"""
        spc = parser(get_file('PTSDY1_largetor10.txt'))
        # spc.draw_outlooks()
        spc.sql(self.txn)
        outlook = spc.get_outlook('TORNADO', '0.10', 1)
        self.assertAlmostEqual(outlook.geometry.area, 31.11, 2)

    def test_170417_empty(self):
        """An empty PTSD48 was causing an exception in get_jabbers"""
        spc = parser(get_file('PTSD48_empty.txt'))
        # spc.draw_outlooks()
        spc.sql(self.txn)
        jabber = spc.get_jabbers('')
        self.assertEquals(jabber[0][0],
                          ("The Storm Prediction Center issues Days 4-8 "
                           "Convective Outlook at Dec 25, 9:41z "
                           "http://www.spc.noaa.gov/products/exper/day4-8/"
                           "archive/2008/day4-8_20081225.html"))

    def test_051128_invalid(self):
        """Make sure that the SIG wind threshold does not eat the US"""
        spc = parser(get_file('PTSDY1_biggeom2.txt'))
        # spc.draw_outlooks()
        spc.sql(self.txn)
        outlook = spc.get_outlook('WIND', 'SIGN', 1)
        self.assertTrue(outlook.geometry.is_empty)
        self.assertEquals(len(spc.warnings), 2, "\n".join(spc.warnings))

    def test_080731_invalid(self):
        """Make sure that the SIG wind threshold does not eat the US"""
        spc = parser(get_file('PTSDY1_biggeom.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('WIND', 'SIGN', 1)
        self.assertAlmostEquals(outlook.geometry.area, 15.82, 2)
        self.assertEquals(len(spc.warnings), 1)

    def test_170411_jabber_error(self):
        """This empty Fire Weather Day 3-8 raised a jabber error"""
        spc = parser(get_file('PFWF38_empty.txt'))
        j = spc.get_jabbers('')
        self.assertEquals(j[0][0],
                          ("The Storm Prediction Center issues Day 3-8 Fire "
                           "Weather Outlook at Apr 11, 19:54z "
                           "http://www.spc.noaa.gov/products/fire_wx/"
                           "2017/20170413.html"))

    def test_170406_day48_pre2015(self):
        """Can we parse a pre2015 days 4-8"""
        spc = parser(get_file('PTSD48_pre2015.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('ANY SEVERE', '0.15', 4)
        self.assertAlmostEqual(outlook.geometry.area, 73.20, 2)
        outlook = spc.get_outlook('ANY SEVERE', '0.15', 5)
        self.assertAlmostEqual(outlook.geometry.area, 76.46, 2)

        spc.sql(self.txn)

    def test_170406_day48(self):
        """Can we parse a present day days 4-8"""
        spc = parser(get_file('PTSD48.txt'))
        # spc.draw_outlooks()
        outlook = spc.get_outlook('ANY SEVERE', '0.15', 4)
        self.assertAlmostEqual(outlook.geometry.area, 40.05, 2)

        spc.sql(self.txn)

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
        collect = spc.get_outlookcollection(3)
        self.assertEquals(len(collect.outlooks), 1)

    def test_bug_140507_day1(self):
        ''' Bug found in production with GEOS Topology Exception '''
        spc = parser(get_file('PTSDY1_topoexp.txt'))
        # spc.draw_outlooks()
        collect = spc.get_outlookcollection(1)
        self.assertEquals(len(collect.outlooks), 14)

    def test_bug_140506_day2(self):
        """Bug found in production"""
        spc = parser(get_file('PTSDY2.txt'))
        # spc.draw_outlooks()
        collect = spc.get_outlookcollection(2)
        self.assertEquals(len(collect.outlooks), 6)
        j = spc.get_jabbers('localhost', 'localhost')
        self.assertEquals(j[0][0],
                          ('The Storm Prediction Center issues Day 2 '
                           'Convective Outlook at May 6, 17:31z '
                           'http://www.spc.noaa.gov/products/outlook/'
                           'archive/2014/day2otlk_20140506_1730.html'))

    def test_bug_140518_day2(self):
        ''' 18 May 2014 tripped error with no exterior polygon found '''
        spc = parser(get_file('PTSDY2_interior.txt'))
        # spc.draw_outlooks()
        collect = spc.get_outlookcollection(2)
        self.assertEquals(len(collect.outlooks), 1)

    def test_bug_140519_day1(self):
        ''' 19 May 2014 tripped error with no exterior polygon found '''
        spc = parser(get_file('PTSDY1_interior.txt'))
        # spc.draw_outlooks()
        collect = spc.get_outlookcollection(1)
        self.assertEquals(len(collect.outlooks), 7)

    def test_bug(self):
        ''' Test bug list index outof range '''
        spc = parser(get_file('PTSDY1_2.txt'))
        collect = spc.get_outlookcollection(1)
        self.assertEquals(len(collect.outlooks), 1)

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
        self.assertEqual(spc.valid, utc(2013, 7, 19, 19, 52))
        self.assertEqual(spc.issue, utc(2013, 7, 19, 20, 0))
        self.assertEqual(spc.expire, utc(2013, 7, 20, 12, 0))

        spc.sql(self.txn)
        spc.compute_wfos(self.txn)
        # It is difficult to get a deterministic result here as in Travis, we
        # don't have UGCS, so the WFO lookup yields no results
        j = spc.get_jabbers("")
        self.assertTrue(len(j) >= 1)
