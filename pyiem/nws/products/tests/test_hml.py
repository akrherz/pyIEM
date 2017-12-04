"""HML"""
from __future__ import print_function
import os
import unittest
import datetime

import psycopg2.extras
from pyiem.nws.products.hml import parser as hmlparser
from pyiem.util import get_dbconn


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


class TestHML(unittest.TestCase):
    """ Tests """
    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = get_dbconn('hads')
        # Note the usage of RealDictCursor here, as this is what
        # pyiem.twistedpg uses
        self.txn = self.dbconn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def tearDown(self):
        ''' This is called after each test, beware '''
        self.dbconn.rollback()
        self.dbconn.close()

    def test_160826_hmlarx(self):
        """Lets dance"""
        prod = hmlparser(get_file("HMLARX.txt"))
        prod.sql(self.txn)
        self.assertEquals(len(prod.warnings), 0,
                          '\n'.join(prod.warnings))

        self.assertEquals(prod.data[0].stationname,
                          "CEDAR RIVER 2 S St. Ansgar")

    def test_161010_timing(self):
        """test how fast we can parse the file, over and over again"""
        sts = datetime.datetime.now()
        for _ in range(100):
            _ = hmlparser(get_file("HMLARX.txt"))
        ets = datetime.datetime.now()
        rate = (ets - sts).total_seconds() / 100.
        print("sec per parse %.4f" % (rate,))
        self.assertTrue(rate < 1.)
