"""Testing FFG parsing."""
import os

import psycopg2.extras
import pytest
from pyiem.nws.products.ffg import parser as ffgparser
from pyiem.util import get_dbconn


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


@pytest.fixture
def dbcursor():
    """Return a database cursor."""
    return get_dbconn('postgis').cursor(
        cursor_factory=psycopg2.extras.DictCursor)


def test_ffg(dbcursor):
    """FFG"""
    prod = ffgparser(get_file('FFGJAN.txt'))
    prod.sql(dbcursor)
    assert len(prod.data.index) == 53


def test_ffg2(dbcursor):
    """FFGKY"""
    prod = ffgparser(get_file('FFGKY.txt'))
    prod.sql(dbcursor)
    assert len(prod.data.index) == 113


def test_ffgama(dbcursor):
    """FFGAMA"""
    prod = ffgparser(get_file('FFGAMA.txt'))
    prod.sql(dbcursor)
    assert len(prod.data.index) == 23
