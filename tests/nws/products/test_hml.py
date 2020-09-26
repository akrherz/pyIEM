"""HML"""
# pylint: disable=redefined-outer-name
import datetime

import psycopg2.extras
import pytest
from pyiem.nws.products.hml import parser as hmlparser
from pyiem.util import get_dbconn, get_test_file, utc


@pytest.fixture
def dbcursor():
    """Get database conn."""
    dbconn = get_dbconn("hml")
    # Note the usage of RealDictCursor here, as this is what
    # pyiem.twistedpg uses
    yield dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    dbconn.close()


def test_200926_nokey(dbcursor):
    """Test that we add a new observation key, when necessary."""
    prod = hmlparser(get_test_file("HML/HMLMOB.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT key from hml_observed_data WHERE station = 'EFRA1' "
        "and valid >= '2020-09-26 13:36+00' and valid < '2020-09-26 13:43+00' "
        "and key is null"
    )
    assert dbcursor.rowcount == 0


def test_190313_missingstage(dbcursor):
    """Figure out why this HML is missing stage info."""
    prod = hmlparser(get_test_file("HML/HMLDMX.txt"))
    assert not prod.warnings
    prod.sql(dbcursor)
    dbcursor.execute(
        """
        SELECT * from hml_observed_data WHERE station = 'JANI4'
        and valid > '2019-03-13' and valid < '2019-03-14'
    """
    )
    assert dbcursor.rowcount == 8


def test_160826_hmlarx(dbcursor):
    """Lets dance"""
    utcnow = utc(2016, 8, 26, 8)
    prod = hmlparser(get_test_file("HML/HMLARX.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    assert not prod.warnings
    assert prod.data[0].stationname == "CEDAR RIVER 2 S St. Ansgar"


def test_161010_timing():
    """test how fast we can parse the file, over and over again"""
    sts = datetime.datetime.now()
    for _ in range(100):
        hmlparser(get_test_file("HML/HMLARX.txt"))
    ets = datetime.datetime.now()
    rate = (ets - sts).total_seconds() / 100.0
    print("sec per parse %.4f" % (rate,))
    assert rate < 1.0
