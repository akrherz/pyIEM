"""See if we can do stuff with the network"""

import psycopg2.extras
import pytest
from pyiem import network
from pyiem.util import get_dbconn


@pytest.fixture
def dbcursor():
    """With each test"""
    conn = get_dbconn('mesosite')
    cursor = conn.cursor(
        cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""INSERT into stations(id, name, network)
    VALUES ('BOGUS', 'BOGUS NAME', 'BOGUS') RETURNING iemid""")
    iemid = cursor.fetchone()[0]
    cursor.execute("""
        INSERT into station_attributes(iemid, attr, value)
        VALUES (%s, 'A', 'AA'), (%s, 'B', 'BB')
    """, (iemid, iemid))
    cursor.execute("""INSERT into stations(id, name, network)
    VALUES ('BOGUS2', 'BOGUS2 NAME', 'BOGUS')""")
    cursor.execute("""INSERT into stations(id, name, network)
    VALUES ('BOGUS3', 'BOGUS3 NAME', 'BOGUS2')""")
    return cursor


def test_basic(dbcursor):
    ''' basic test of constructor '''
    nt = network.Table("BOGUS", cursor=dbcursor)
    assert len(nt.sts.keys()) == 2

    nt = network.Table(["BOGUS", "BOGUS2"], cursor=dbcursor)
    assert len(nt.sts.keys()) == 3

    assert nt.sts['BOGUS']['name'] == 'BOGUS NAME'
    assert len(nt.sts['BOGUS']['attributes']) == 2
    assert not nt.sts['BOGUS2']['attributes']

    nt = network.Table(["BOGUS", "BOGUS2"])
    assert not nt.sts.keys()
