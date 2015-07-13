import os
import datetime
import pytz
import unittest
from pyiem.nws.products.saw import parser as sawparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/SAW/%s" % (basedir, name)
    return open(fn).read()


class TestProducts(unittest.TestCase):
    """ Tests """

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
