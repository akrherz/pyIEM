import unittest
import datetime
import os

from pyiem import mrms


class TestDatatypes(unittest.TestCase):

    def test_get_fn(self):
        """ Test filename func """
        ts = datetime.datetime(2000, 1, 1, 12, 35)
        fn = mrms.get_fn('p24h', ts, 3)
        expected = ("/mnt/a4/data/2000/01/01/mrms/tile3/p24h/"
                    "p24h.20000101.123500.gz")
        self.assertEqual(fn, expected)

    def test_reader(self):
        """Can we read the legacy file """
        fn = ("%s/../../data/product_examples/1hrad.20130920.190000.gz"
              ) % (os.path.dirname(__file__), )
        metadata, _ = mrms.reader(fn)
        self.assertAlmostEquals(metadata['ul_lat'], 54.99, 2)
