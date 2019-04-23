"""HML"""
from __future__ import print_function
import datetime

import psycopg2.extras
import pytest
from pyiem.nws.products.hml import parser as hmlparser
from pyiem.util import get_dbconn, get_test_file


@pytest.fixture
def dbcursor():
    """Get database conn."""
    dbconn = get_dbconn('hads')
    # Note the usage of RealDictCursor here, as this is what
    # pyiem.twistedpg uses
    return dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)


def test_190313_missingstage(dbcursor):
    """Figure out why this HML is missing stage info."""
    prod = hmlparser(get_test_file("HML/HMLDMX.txt"))
    assert not prod.warnings
    prod.sql(dbcursor)
    dbcursor.execute("""
        SELECT * from hml_observed_data_2019 WHERE station = 'JANI4'
        and valid > '2019-03-13' and valid < '2019-03-14'
    """)
    assert dbcursor.rowcount == 8


def test_160826_hmlarx(dbcursor):
    """Lets dance"""
    prod = hmlparser(get_test_file("HML/HMLARX.txt"))
    prod.sql(dbcursor)
    assert not prod.warnings
    assert prod.data[0].stationname == "CEDAR RIVER 2 S St. Ansgar"


def test_161010_timing():
    """test how fast we can parse the file, over and over again"""
    sts = datetime.datetime.now()
    for _ in range(100):
        hmlparser(get_test_file("HML/HMLARX.txt"))
    ets = datetime.datetime.now()
    rate = (ets - sts).total_seconds() / 100.
    print("sec per parse %.4f" % (rate,))
    assert rate < 1.
