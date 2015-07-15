import unittest
from pyiem import network


class TestNetwork(unittest.TestCase):

    def test_basic(self):
        ''' basic test of constructor '''
        nt = network.Table("BOGUS")
        self.assertEqual(len(nt.sts.keys()), 0)
