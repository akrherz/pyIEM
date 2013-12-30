import unittest
import datetime

from pyiem import mrms

class TestDatatypes(unittest.TestCase):

    def test_get_fn(self):
        ''' Test filename func '''
        ts = datetime.datetime(2000,1,1,12,35)
        fn = mrms.get_fn('p24h', ts, 3)
        expected = ("/mnt/a4/data/2000/01/01/mrms/tile3/p24h/"
                +"p24h.20000101.123500.gz")
        self.assertEqual( fn, expected)
