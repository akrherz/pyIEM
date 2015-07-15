import unittest
import datetime
import pytz
import psycopg2.extras

from pyiem import observation


class TestObservation(unittest.TestCase):

    def setUp(self):
        ts = datetime.datetime.utcnow()
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.ob = observation.Observation('DSM', 'IA_ASOS', ts)
        self.conn = psycopg2.connect(database='iem', host='iemdb')
        self.cursor = self.conn.cursor(
                        cursor_factory=psycopg2.extras.DictCursor)

    def test_simple(self):
        """ Simple check of observation """
        self.assertTrue(self.ob)

    def test_update(self):
        """ Make sure we can update the database """
        _ = self.ob.save(self.cursor)
        self.assertTrue(True)
