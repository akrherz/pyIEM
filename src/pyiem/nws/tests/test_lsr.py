import unittest
import os

from pyiem.nws.lsr import LSRProduct, LSR, LSRProductException
from pyiem.nws.lsr import parser as lsrparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestLSR(unittest.TestCase):
    
    def test_01(self):
        """ process a valid LSR without blemish """
        prod = lsrparser( get_file("LSR.txt") )
        self.assertEqual(len(prod.lsrs), 58)
        
        self.assertEqual(prod.lsrs[57].magnitude, 73)
        self.assertEqual(prod.lsrs[57].county, "MARION")
        self.assertEqual(prod.lsrs[57].state, "IA")
        self.assertAlmostEqual(prod.lsrs[57].get_lon(), -93.11, 2)
        self.assertAlmostEqual(prod.lsrs[57].get_lat(), 41.3, 1)
        
        self.assertEqual(prod.is_summary(), True)
        self.assertEqual(prod.lsrs[57].wfo , 'DMX')
        
        self.assertEqual(prod.lsrs[57].jabber_text(), ("KNOXVILLE AIRPORT "
        +"[MARION Co, IA] AWOS reports NON-TSTM WND GST at 22 Jul, "
        +"10:55 PM CST -- HEAT BURST. TEMPERATURE ROSE FROM 70 TO 84 IN "
        +"15 MINUTES AND DEW POINT DROPPED FROM 63 TO 48 IN 10 MINUTES. "
        +"http://localhost"))