"""MCD/MPD tests"""
import unittest
import os

import psycopg2.extras
from pyiem.nws.products.mcd import parser
from pyiem.util import get_dbconn, utc


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/MCD_MPD/%s" % (basedir, name)
    return open(fn, 'rb').read().decode('utf-8')


class TestMCD(unittest.TestCase):

    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = get_dbconn('postgis')
        # Note the usage of RealDictCursor here, as this is what
        # pyiem.twistedpg uses
        self.txn = self.dbconn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def tearDown(self):
        ''' This is called after each test, beware '''
        self.dbconn.rollback()
        self.dbconn.close()

    def test_170926_nodbinsert(self):
        """This product never hit the database for some reason?"""
        prod = parser(get_file('SWOMCD_2010.txt'))
        prod.database_save(self.txn)
        self.txn.execute("""
            SELECT * from text_products where product_id = %s
        """, (prod.get_product_id(), ))
        self.assertEquals(self.txn.rowcount, 1)

    def test_mpd_mcdparser(self):
        ''' The mcdparser can do WPC's MPD as well, test it '''
        prod = parser(get_file('MPD.txt'))
        self.assertAlmostEqual(prod.geometry.area, 4.657, 3)
        self.assertEqual(prod.attn_wfo, ['PHI', 'AKQ', 'CTP', 'LWX'])
        self.assertEqual(prod.attn_rfc, ['MARFC'])
        self.assertEqual(prod.tweet(), (
            '#WPC issues MPD 98: NRN VA...D.C'
            '....CENTRAL MD INTO SERN PA '
            'http://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php'
            '?md=98&yr=2013'))
        # self.assertEqual(prod.find_cwsus(self.txn), ['ZDC', 'ZNY'])
        self.assertEqual(prod.get_jabbers('http://localhost')[0][0], (
            'Weather Prediction Center issues '
            'Mesoscale Precipitation Discussion #98'
            ' http://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php'
            '?md=98&amp;yr=2013'))

        prod.database_save(self.txn)

    def test_mcdparser(self):
        ''' Test Parsing of MCD Product '''
        prod = parser(get_file('SWOMCD.txt'))
        self.assertAlmostEqual(prod.geometry.area, 4.302, 3)
        self.assertEqual(prod.discussion_num, 1525)
        self.assertEqual(prod.attn_wfo[2], 'DLH')
        self.assertEqual(prod.areas_affected, ("PORTIONS OF NRN WI AND "
                                               "THE UPPER PENINSULA OF MI"))

        # With probability this time
        prod = parser(get_file('SWOMCDprob.txt'))
        self.assertAlmostEqual(prod.geometry.area, 2.444, 3)
        self.assertEqual(prod.watch_prob, 20)

        jmsg = prod.get_jabbers('http://localhost')
        self.assertEqual(jmsg[0][1], (
            '<p>Storm Prediction Center issues '
            '<a href="http://www.spc.noaa.gov/'
            'products/md/2013/md1678.html">Mesoscale Discussion #1678</a> '
            '[watch probability: 20%] (<a href="http://localhost'
            '?pid=201308091725-KWNS-ACUS11-SWOMCD">View text</a>)</p>'))
        self.assertEqual(jmsg[0][0], (
            'Storm Prediction Center issues Mesoscale Discussion #1678 '
            '[watch probability: 20%] '
            'http://www.spc.noaa.gov/products/md/2013/md1678.html'))
        answer = utc(2013, 8, 9, 17, 25)
        self.assertEquals(prod.sts, answer)
        answer = utc(2013, 8, 9, 19, 30)
        self.assertEquals(prod.ets, answer)

        prod.database_save(self.txn)
