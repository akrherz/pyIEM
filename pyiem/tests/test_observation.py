"""Test Observation"""
import unittest
import string
import random

import psycopg2.extras

from pyiem import observation
from pyiem.util import get_dbconn, utc


def test_calc():
    """Can we compute feels like and RH?"""
    ts = utc(2018)
    ob = observation.Observation('FAKE', 'FAKE', ts)
    ob.data['tmpf'] = 89.
    ob.data['dwpf'] = 70.
    ob.data['sknt'] = 10.
    ob.calc()
    assert (ob.data['feel'] - 94.3) < 0.1
    assert (ob.data['relh'] - 53.6) < 0.1


class TestObservation(unittest.TestCase):
    """Some tests"""

    def setUp(self):
        ts = utc(2015, 9, 1, 1, 0)
        sid = ''.join(random.choice(
                    string.ascii_uppercase + string.digits) for _ in range(7))
        self.iemid = 0 - random.randint(0, 1000)
        self.ob = observation.Observation(sid, 'FAKE', ts)
        self.conn = get_dbconn('iem')
        self.cursor = self.conn.cursor(
                        cursor_factory=psycopg2.extras.DictCursor)
        # Create fake station, so we can create fake entry in summary
        # and current tables
        self.cursor.execute("""
            INSERT into stations(id, network, iemid, tzname)
            VALUES (%s, 'FAKE', %s, 'UTC')
        """, (sid, self.iemid))
        self.cursor.execute("""
            INSERT into current(iemid, valid) VALUES
            (%s, '2015-09-01 00:00+00')
        """, (self.iemid, ))
        self.cursor.execute("""
            INSERT into summary_2015(iemid, day) VALUES
            (%s, '2015-09-01')
        """, (self.iemid, ))

    def test_nodata(self):
        """ Make sure we return False when we don't have entries in tables"""
        self.ob.data['station'] = 'HaHaHa'
        response = self.ob.save(self.cursor)
        self.assertFalse(response)

        response = self.ob.load(self.cursor)
        self.assertFalse(response)

    def test_hardcoded_maxtmpf(self):
        """Do we do the right thing when max_tmpf is set."""
        self.ob.data['tmpf'] = 55
        assert self.ob.save(self.cursor, skip_current=True)
        # in the database max_tmpf should be 55 now
        self.cursor.execute("""
            SELECT max_tmpf from summary_2015
            WHERE day = '2015-09-01' and iemid = %s
        """, (self.iemid,))
        assert self.cursor.fetchone()[0] == 55
        # setting max_tmpf to 54 should update it too
        self.ob.data['max_tmpf'] = 54
        assert self.ob.save(self.cursor)
        self.cursor.execute("""
            SELECT max_tmpf from summary_2015
            WHERE day = '2015-09-01' and iemid = %s
        """, (self.iemid,))
        assert self.cursor.fetchone()[0] == 54

    def test_null(self):
        """ Make sure our null logic is working """
        self.ob.data['tmpf'] = 55
        response = self.ob.save(self.cursor)
        self.assertTrue(response)
        assert self.ob.data['dwpf'] is None
        self.ob.data['relh'] = 0
        response = self.ob.save(self.cursor)
        assert self.ob.data['dwpf'] is None
        self.ob.data['relh'] = 50
        response = self.ob.save(self.cursor)
        assert abs(self.ob.data['dwpf'] - 36.71) < 0.2
        self.cursor.execute("""SELECT max_tmpf from summary_2015
        WHERE day = '2015-09-01' and iemid = %s""", (self.iemid,))
        self.assertEqual(self.cursor.rowcount, 1)
        self.assertEqual(self.cursor.fetchone()[0], 55)

    def test_update(self):
        """ Make sure we can update the database """
        response = self.ob.load(self.cursor)
        self.assertFalse(response)
        self.ob.data['valid'] = self.ob.data['valid'].replace(hour=0)
        response = self.ob.load(self.cursor)
        self.assertTrue(response)

        response = self.ob.save(self.cursor)
        self.assertTrue(response)

        response = self.ob.save(self.cursor, force_current_log=True)
        self.assertTrue(response)
