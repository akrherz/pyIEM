"""Test MOS Parsing"""
import os
import unittest
import datetime

import pytz
import psycopg2.extras
from pyiem.nws.products.mos import parser as tafparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/MOS/%s" % (basedir, name)
    return open(fn, 'rb').read().decode('utf-8')


class TestProducts(unittest.TestCase):
    """ Tests """

    def setUp(self):
        self.conn = psycopg2.connect(database='mos', host='iemdb')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def test_parse(self):
        """MOS type"""
        utcnow = datetime.datetime(2017, 8, 12, 12).replace(tzinfo=pytz.utc)
        prod = tafparser(get_file("METNC1.txt"), utcnow=utcnow)
        self.assertEquals(len(prod.data), 4)
        self.assertEquals(len(prod.data[0]['data'].keys()), 21)

        inserts = prod.sql(self.cursor)
        self.assertEquals(inserts, 4 * 21)
