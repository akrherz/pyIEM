"""tests of twistedpg."""

from psycopg2.extras import DictCursor
from pyiem import twistedpg


def test_connect():
    """Does our logic work?"""
    conn = twistedpg.connect(database="postgis", host="iemdb.local")
    cursor = conn.cursor()
    assert isinstance(cursor, DictCursor)
