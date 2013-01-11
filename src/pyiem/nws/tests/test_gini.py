import unittest
from pyiem.nws import gini
import os

class TestObservation(unittest.TestCase):
    
    def test_gini(self):
        """ check GINI Processing of Goes East VIS parsing """
        # This fn may not be available
        fn = "data/product_examples/TIGE01"
        if not os.path.isfile(fn):
            return
        sat = gini.GINIZFile( open(fn) )
        
        self.assertEqual(sat.archive_filename(), "GOES_EAST_VIS_201301111601.png")