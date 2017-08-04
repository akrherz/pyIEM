"""Test TAF Parsing"""
import os
import unittest
import datetime

import pytz
from pyiem.nws.products.taf import parser as tafparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/TAF/%s" % (basedir, name)
    return open(fn).read()


class TestProducts(unittest.TestCase):
    """ Tests """

    def test_parse(self):
        """TAF type"""
        utcnow = datetime.datetime(2017, 7, 25).replace(tzinfo=pytz.utc)
        prod = tafparser(get_file("TAFJFK.txt"), utcnow=utcnow)
        j = prod.get_jabbers("http://localhost", "http://localhost")
        self.assertEquals(j[0][0],
                          ("OKX issues Terminal Aerodrome Forecast (TAF) "
                           "for JFK http://localhost?"
                           "pid=201707251341-KOKX-FTUS41-TAFJFK"))
        assert "TAFJFK" in j[0][2]['channels'].split(",")
