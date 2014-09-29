import os
import datetime
import pytz
import unittest
from pyiem.nws.products.cli import parser as cliparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()



class TestProducts(unittest.TestCase):
    """ Tests """
    
    def test_cli(self):
        """ Test the processing of a CLI product """
        prod = cliparser(get_file('CLIJNU.txt'))
        self.assertEqual(prod.cli_valid, datetime.datetime(2013,6,30))
        self.assertEqual(prod.valid, datetime.datetime(2013,7,1,0,36).replace(
                                    tzinfo=pytz.timezone("UTC")))
        self.assertEqual(prod.data['temperature_maximum'], 75)
        self.assertEqual(prod.data['precip_today'], 0.0001)
        
        prod = cliparser(get_file('CLIDSM.txt'))
        self.assertEqual(prod.cli_valid, datetime.datetime(2013,8,1))
        self.assertEqual(prod.data['temperature_maximum'], 89)
        self.assertEqual(prod.data['snow_month'], 0)
        self.assertEqual(prod.data['temperature_minimum_record_year'], 1898)
        self.assertEqual(prod.data['snow_today'], 0)