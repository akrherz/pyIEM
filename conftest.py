"""Centralized Testing Stuff."""

# third party
import pytest
from psycopg2.extras import DictCursor

# This repo
from pyiem.util import get_dbconn


@pytest.fixture()
def dbcursor(database):
    """Yield a cursor for the given database."""
    dbconn = get_dbconn(database)
    yield dbconn.cursor(cursor_factory=DictCursor)
    dbconn.close()
