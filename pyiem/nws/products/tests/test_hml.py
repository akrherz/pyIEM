import os
import datetime
import pytz
import psycopg2.extras
import unittest
from pyiem.nws.products.hml import parser as hmlparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour, minute).replace(
                        tzinfo=pytz.timezone("UTC"))


class TestProducts(unittest.TestCase):
    """ Tests """
    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = psycopg2.connect(database='hads')
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
