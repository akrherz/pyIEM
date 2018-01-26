"""Test MOS Parsing"""
import os
import unittest

import psycopg2.extras
from pyiem.nws.products.mos import parser as tafparser
from pyiem.util import get_dbconn, utc


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/MOS/%s" % (basedir, name)
    return open(fn, 'rb').read().decode('utf-8')


class TestProducts(unittest.TestCase):
    """ Tests """

    def setUp(self):
        self.conn = get_dbconn('mos')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def test_180125_empty(self):
        """Can we parse a MOS product with empty data"""
        utcnow = utc(2018, 1, 26, 1)
        prod = tafparser(get_file("MET_empty.txt"), utcnow=utcnow)
        self.assertEquals(len(prod.data), 3)
        self.assertEquals(len(prod.data[0]['data'].keys()), 21)

        inserts = prod.sql(self.cursor)
        self.assertEquals(inserts, 42)

    def test_parse(self):
        """MOS type"""
        utcnow = utc(2017, 8, 12, 12)
        prod = tafparser(get_file("METNC1.txt"), utcnow=utcnow)
        self.assertEquals(len(prod.data), 4)
        self.assertEquals(len(prod.data[0]['data'].keys()), 21)

        inserts = prod.sql(self.cursor)
        self.assertEquals(inserts, 4 * 21)
