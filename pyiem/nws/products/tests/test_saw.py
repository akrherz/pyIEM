"""Can we process the SAW"""
import os
import datetime
import unittest

import psycopg2.extras
import pytz
from pyiem.nws.products.saw import parser as sawparser
from pyiem.util import get_dbconn


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/SAW/%s" % (basedir, name)
    return open(fn).read()


class TestProducts(unittest.TestCase):
    """ Tests """

    def setUp(self):
        self.conn = get_dbconn('postgis')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def test_replacement(self):
        """Can we do replacements?"""
        utcnow = datetime.datetime(2017, 8, 21, 9, 17)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = sawparser(get_file('SAW-replaces.txt'), utcnow=utcnow)
        prod.sql(self.cursor)
        jmsgs = prod.get_jabbers('')
        self.assertEquals(len(jmsgs), 1)
        self.assertEquals(jmsgs[0][0],
                          ("SPC issues Severe Thunderstorm Watch"
                           " 153 till 17:00Z, new watch replaces WW 1 "
                           "http://www.spc.noaa.gov/products/watch/"
                           "2017/ww0153.html"))

    def test_saw3(self):
        """SAW3"""
        utcnow = datetime.datetime(2014, 3, 10, 3, 29)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        sts = utcnow.replace(hour=3, minute=35)
        ets = utcnow.replace(hour=9, minute=0)
        prod = sawparser(get_file('SAW3.txt'), utcnow=utcnow)
        self.assertEquals(prod.saw, 3)
        self.assertAlmostEquals(prod.geometry.area, 7.73, 2)
        self.assertEquals(prod.ww_num, 503)
        self.assertEquals(prod.sts, sts)
        self.assertEquals(prod.ets, ets)
        self.assertEquals(prod.ww_type, prod.SEVERE_THUNDERSTORM)
        self.assertEquals(prod.action, prod.ISSUES)

    def test_cancelled(self):
        """SAW-cancelled make sure we can cancel a watch"""
        utcnow = datetime.datetime(2014, 3, 10, 3, 29)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = sawparser(get_file('SAW-cancelled.txt'), utcnow=utcnow)
        self.assertEquals(prod.action, prod.CANCELS)
        j = prod.get_jabbers(None)
        answer = ("Storm Prediction Center cancels Weather Watch Number 575 "
                  "http://www.spc.noaa.gov/products/watch/2014/ww0575.html")
        self.assertEquals(j[0][0], answer)
        prod.sql(self.cursor)
        prod.compute_wfos(self.cursor)
