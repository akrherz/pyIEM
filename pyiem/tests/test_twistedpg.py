"""tests"""
import unittest

from pyiem import twistedpg
from psycopg2.extras import DictCursor


class TestTWPG(unittest.TestCase):
    """Our tests"""

    def test_connect(self):
        """Does our logic work?"""
        conn = twistedpg.connect(database='postgis', host='iemdb')
        cursor = conn.cursor()
        self.assertTrue(isinstance(cursor, DictCursor))
