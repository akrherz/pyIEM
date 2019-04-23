"""Test Observation"""
import string
import random

import psycopg2.extras
import pytest
from pyiem import observation
from pyiem.util import get_dbconn, utc


class blah:
    """pass"""
    iemid = None
    ob = None
    conn = None
    cursor = None


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


@pytest.fixture
def iemob():
    """Database."""
    res = blah()
    ts = utc(2015, 9, 1, 1, 0)
    sid = ''.join(random.choice(
                string.ascii_uppercase + string.digits) for _ in range(7))
    res.iemid = 0 - random.randint(0, 1000)
    res.ob = observation.Observation(sid, 'FAKE', ts)
    res.conn = get_dbconn('iem')
    res.cursor = res.conn.cursor(
        cursor_factory=psycopg2.extras.DictCursor)
    # Create fake station, so we can create fake entry in summary
    # and current tables
    res.cursor.execute("""
        INSERT into stations(id, network, iemid, tzname)
        VALUES (%s, 'FAKE', %s, 'UTC')
    """, (sid, res.iemid))
    res.cursor.execute("""
        INSERT into current(iemid, valid) VALUES
        (%s, '2015-09-01 00:00+00')
    """, (res.iemid, ))
    res.cursor.execute("""
        INSERT into summary_2015(iemid, day) VALUES
        (%s, '2015-09-01')
    """, (res.iemid, ))
    return res


def test_nodata(iemob):
    """ Make sure we return False when we don't have entries in tables"""
    iemob.ob.data['station'] = 'HaHaHa'
    response = iemob.ob.save(iemob.cursor)
    assert not response

    response = iemob.ob.load(iemob.cursor)
    assert not response


def test_hardcoded_maxtmpf(iemob):
    """Do we do the right thing when max_tmpf is set."""
    iemob.ob.data['tmpf'] = 55
    assert iemob.ob.save(iemob.cursor, skip_current=True)
    # in the database max_tmpf should be 55 now
    iemob.cursor.execute("""
        SELECT max_tmpf from summary_2015
        WHERE day = '2015-09-01' and iemid = %s
    """, (iemob.iemid,))
    assert iemob.cursor.fetchone()[0] == 55
    # setting max_tmpf to 54 should update it too
    iemob.ob.data['max_tmpf'] = 54
    assert iemob.ob.save(iemob.cursor)
    iemob.cursor.execute("""
        SELECT max_tmpf from summary_2015
        WHERE day = '2015-09-01' and iemid = %s
    """, (iemob.iemid,))
    assert iemob.cursor.fetchone()[0] == 54


def test_null(iemob):
    """ Make sure our null logic is working """
    iemob.ob.data['tmpf'] = 55
    response = iemob.ob.save(iemob.cursor)
    assert response
    assert iemob.ob.data['dwpf'] is None
    iemob.ob.data['relh'] = 0
    response = iemob.ob.save(iemob.cursor)
    assert iemob.ob.data['dwpf'] is None
    iemob.ob.data['relh'] = 50
    response = iemob.ob.save(iemob.cursor)
    assert abs(iemob.ob.data['dwpf'] - 36.71) < 0.2
    iemob.cursor.execute("""SELECT max_tmpf from summary_2015
    WHERE day = '2015-09-01' and iemid = %s""", (iemob.iemid,))
    assert iemob.cursor.rowcount == 1
    assert iemob.cursor.fetchone()[0] == 55


def test_update(iemob):
    """ Make sure we can update the database """
    response = iemob.ob.load(iemob.cursor)
    assert not response
    iemob.ob.data['valid'] = iemob.ob.data['valid'].replace(hour=0)
    response = iemob.ob.load(iemob.cursor)
    assert response

    response = iemob.ob.save(iemob.cursor)
    assert response

    response = iemob.ob.save(iemob.cursor, force_current_log=True)
    assert response
