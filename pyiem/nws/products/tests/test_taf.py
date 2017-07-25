"""Test TAF Parsing"""
import os
import unittest

from pyiem.nws.products.taf import parser as nhcparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/TAF/%s" % (basedir, name)
    return open(fn).read()


class TestProducts(unittest.TestCase):
    """ Tests """

    def test_parse(self):
        """TAF type"""
        prod = nhcparser(get_file("TAFJFK.txt"))
        j = prod.get_jabbers("http://localhost", "http://localhost")
        self.assertEquals(j[0][0],
                          ("OKX issues Terminal Aerodrome Forecast (TAF) "
                           "for JFK http://localhost?"
                           "pid=201707251341-KOKX-FTUS41-TAFJFK"))
        assert "TAFJFK" in j[0][2]['channels'].split(",")
