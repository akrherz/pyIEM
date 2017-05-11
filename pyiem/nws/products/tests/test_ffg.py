"""Testing FFG parsing"""
import os
import unittest

import psycopg2.extras
from pyiem.nws.products.ffg import parser as ffgparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


class TestFFG(unittest.TestCase):
    """ Tests """
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

    def test_ffg(self):
        """FFG"""
        prod = ffgparser(get_file('FFGJAN.txt'))
        prod.sql(self.txn)
        self.assertEquals(len(prod.data.index), 53)

    def test_ffg2(self):
        """FFGKY"""
        prod = ffgparser(get_file('FFGKY.txt'))
        prod.sql(self.txn)
        self.assertEquals(len(prod.data.index), 113)

    def test_ffgama(self):
        """FFGAMA"""
        prod = ffgparser(get_file('FFGAMA.txt'))
        prod.sql(self.txn)
        self.assertEquals(len(prod.data.index), 23)
