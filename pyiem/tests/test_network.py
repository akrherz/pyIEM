"""See if we can do stuff with the network"""
import unittest

import psycopg2.extras
from pyiem import network


class TestNetwork(unittest.TestCase):
    """Test Cases Please"""

    def setUp(self):
        """With each test"""
        self.conn = psycopg2.connect(database='mesosite', host='iemdb')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)
        self.cursor.execute("""INSERT into stations(id, name, network)
        VALUES ('BOGUS', 'BOGUS NAME', 'BOGUS') RETURNING iemid""")
        self.cursor.execute("""INSERT into stations(id, name, network)
        VALUES ('BOGUS2', 'BOGUS2 NAME', 'BOGUS')""")
        self.cursor.execute("""INSERT into stations(id, name, network)
        VALUES ('BOGUS3', 'BOGUS3 NAME', 'BOGUS2')""")

    def test_basic(self):
        ''' basic test of constructor '''
        nt = network.Table("BOGUS", cursor=self.cursor)
        self.assertEqual(len(nt.sts.keys()), 2)

        nt = network.Table(["BOGUS", "BOGUS2"], cursor=self.cursor)
        self.assertEqual(len(nt.sts.keys()), 3)

        self.assertEqual(nt.sts['BOGUS']['name'], 'BOGUS NAME')

        nt = network.Table(["BOGUS", "BOGUS2"])
        self.assertEqual(len(nt.sts.keys()), 0)
