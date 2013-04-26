import unittest

from pyiem.nws import parser

class TestObservation(unittest.TestCase):

    def test_111(self):
        """ Check parser """
        engine = parser.Engine()
        res = engine.parse( open('data/product_examples/AFD.txt').read())
        self.assertEqual(res['jabber_msgs'][0].plain, 
                         "BOX issues Area Forecast Discussion (AFD) http://localhost/201211270001-KBOX-FXUS61-AFDBOX")
        self.assertEqual(res['tweets'][0].plain, 
                         "BOX issues Area Forecast Discussion (AFD)")