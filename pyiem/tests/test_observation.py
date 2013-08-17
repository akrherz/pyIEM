import unittest
import datetime
import pytz

from pyiem import observation, iemdb

class TestObservation(unittest.TestCase):

    def setUp(self):
        ts = datetime.datetime.utcnow()
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.ob = observation.Observation('DSM', 'IA_ASOS', ts)
        (self.conn, self.cursor) = iemdb.cnc('iem', host='127.0.0.1')
        
    def test_simple(self):
        """ Simple check of observation """
        self.assertTrue(self.ob)
        
    def test_update(self):
        """ Make sure we can update the database """
        updated = self.ob.save(self.cursor)
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()