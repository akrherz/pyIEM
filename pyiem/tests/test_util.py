import unittest
from pyiem import util

class TestObservation(unittest.TestCase):
    
    def test_drct2text(self):
        """ Test conversion of drct2text """
        self.assertEquals(util.drct2text(360), "N")