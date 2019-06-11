"""See if we can do stuff with the network"""
# pylint: disable=redefined-outer-name

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
    cursor.execute("""
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS', 'BOGUS NAME', 'BOGUS', 't')
        RETURNING iemid
    """)
    iemid = cursor.fetchone()[0]
    cursor.execute("""
        INSERT into station_attributes(iemid, attr, value)
        VALUES (%s, 'A', 'AA'), (%s, 'B', 'BB')
    """, (iemid, iemid))
    cursor.execute("""
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS2', 'BOGUS2 NAME', 'BOGUS', 't')
    """)
    cursor.execute("""
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS3', 'BOGUS3 NAME', 'BOGUS2', 'f')
    """)
    return cursor


def test_basic(dbcursor):
    ''' basic test of constructor '''
    nt = network.Table("BOGUS", cursor=dbcursor)
    assert len(nt.sts.keys()) == 2

    nt = network.Table(["BOGUS", "BOGUS2"], cursor=dbcursor)
    assert len(nt.sts.keys()) == 2

    nt = network.Table(["BOGUS", "BOGUS2"], cursor=dbcursor, only_online=False)
    assert len(nt.sts.keys()) == 3

    assert nt.sts['BOGUS']['name'] == 'BOGUS NAME'
    assert len(nt.sts['BOGUS']['attributes']) == 2
    assert not nt.sts['BOGUS2']['attributes']

    # kind of a lame test here without the local cursor
    nt = network.Table(["BOGUS", "BOGUS2"])
    assert not nt.sts.keys()

    nt = network.Table("BOGUS2", cursor=dbcursor)
    assert not nt.sts.keys()
