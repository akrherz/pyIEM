"""Can we process the SAW"""
import os
import datetime
import unittest

import psycopg2.extras
import pytz
from pyiem.nws.products.saw import parser as sawparser
from pyiem.util import get_dbconn, utc


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/SAW/%s" % (basedir, name)
    return open(fn).read()


def test_181231_linkisok():
    """The plain text tweet should have a space."""
    utcnow = utc(2014, 3, 10, 3, 29)
    prod = sawparser(get_file('SAW3.txt'), utcnow=utcnow)
    jmsgs = prod.get_jabbers('')
    ans = (
        "SPC issues Severe Thunderstorm Watch 503 till 9:00Z "
        "https://www.spc.noaa.gov/products/watch/2014/ww0503.html"
    )
    assert jmsgs[0][0] == ans


class TestProducts(unittest.TestCase):
    """ Tests """

    def setUp(self):
        self.conn = get_dbconn('postgis')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def test_replacement(self):
        """Can we do replacements?"""
        utcnow = datetime.datetime(2017, 8, 21, 9, 17)
        utcnow = utcnow.replace(tzinfo=pytz.UTC)
        prod = sawparser(get_file('SAW-replaces.txt'), utcnow=utcnow)
        prod.sql(self.cursor)
        jmsgs = prod.get_jabbers('')
        self.assertEqual(len(jmsgs), 1)
        self.assertEqual(jmsgs[0][0],
                         ("SPC issues Severe Thunderstorm Watch"
                          " 153 till 17:00Z, new watch replaces WW 1 "
                          "https://www.spc.noaa.gov/products/watch/"
                          "2017/ww0153.html"))
        assert 'twitter' in jmsgs[0][2]

    def test_saw3(self):
        """SAW3"""
        utcnow = datetime.datetime(2014, 3, 10, 3, 29)
        utcnow = utcnow.replace(tzinfo=pytz.UTC)
        sts = utcnow.replace(hour=3, minute=35)
        ets = utcnow.replace(hour=9, minute=0)
        prod = sawparser(get_file('SAW3.txt'), utcnow=utcnow)
        self.assertEqual(prod.saw, 3)
        assert abs(prod.geometry.area - 7.73) < 0.01
        self.assertEqual(prod.ww_num, 503)
        self.assertEqual(prod.sts, sts)
        self.assertEqual(prod.ets, ets)
        self.assertEqual(prod.ww_type, prod.SEVERE_THUNDERSTORM)
        self.assertEqual(prod.action, prod.ISSUES)

    def test_cancelled(self):
        """SAW-cancelled make sure we can cancel a watch"""
        utcnow = datetime.datetime(2014, 3, 10, 3, 29)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = sawparser(get_file('SAW-cancelled.txt'), utcnow=utcnow)
        self.assertEqual(prod.action, prod.CANCELS)
        j = prod.get_jabbers(None)
        answer = ("Storm Prediction Center cancels Weather Watch Number 575 "
                  "https://www.spc.noaa.gov/products/watch/2014/ww0575.html")
        self.assertEqual(j[0][0], answer)
        prod.sql(self.cursor)
        prod.compute_wfos(self.cursor)
