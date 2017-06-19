import os
import unittest
from pyiem.nws.products.nhc import parser as nhcparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


class TestProducts(unittest.TestCase):
    """ Tests """

    def test_170618_potential(self):
        """New TCP type"""
        prod = nhcparser(get_file("TCPAT2.txt"))
        self.assertEquals(len(prod.warnings), 0,
                          '\n'.join(prod.warnings))
        j = prod.get_jabbers("http://localhost", "http://localhost")
        self.assertEquals(j[0][0],
                          ("National Hurricance Center issues ADVISORY 2 "
                           "for POTENTIAL TROPICAL CYCLONE TWO "
                           "http://localhost?"
                           "pid=201706190300-KNHC-WTNT32-TCPAT2"))

    def test_160905_correction(self):
        """See that a product correction does not trip us"""
        prod = nhcparser(get_file("TCPAT4.txt"))
        self.assertEquals(len(prod.warnings), 0,
                          '\n'.join(prod.warnings))
        j = prod.get_jabbers("http://localhost", "http://localhost")
        self.assertEquals(j[0][0],
                          ("National Hurricance Center issues ADVISORY 28A "
                           "for POST-TROPICAL CYCLONE HERMINE INTERMEDIATE "
                           "http://localhost?pid=201609041200"
                           "-KNHC-WTNT34-TCPAT4"))
