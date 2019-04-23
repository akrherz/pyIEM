"""SPS Parsing"""

import pytest
from psycopg2.extras import RealDictCursor
from pyiem.util import get_dbconn, get_test_file
from pyiem.nws.ugc import UGC
from pyiem.nws.products.sps import parser as spsparser


@pytest.fixture
def dbcursor():
    """Get a cursor we can use"""
    pgconn = get_dbconn('postgis')
    return pgconn.cursor(cursor_factory=RealDictCursor)


def test_sps(dbcursor):
    """Can we parse a SPS properly, yes we can!"""
    ugc_provider = {'ALZ039': UGC("AL", "Z", "039", name='Marengo')}
    prod = spsparser(get_test_file('SPSBMX.txt'), ugc_provider=ugc_provider)
    jmsgs = prod.get_jabbers('http://localhost')
    assert len(prod.segments) == 2
    assert len(jmsgs) == 1
    expected = ("<p>BMX issues <a href='http://localhost?pid=201805292152-"
                "KBMX-WWUS84-SPSBMX'>SIGNIFICANT WEATHER ADVISORY FOR "
                "SOUTHWESTERN MARENGO COUNTY UNTIL 515 PM CDT</a></p>")
    assert jmsgs[0][1] == expected
    assert 'SPSBMX' in jmsgs[0][2]['channels']
    assert 'SPS...' in jmsgs[0][2]['channels']
    assert 'SPSBMX.ALZ039' in jmsgs[0][2]['channels']
    assert 'ALZ039' in jmsgs[0][2]['channels']

    prod.sql(dbcursor)
    dbcursor.execute("""
        SELECT count(*) from text_products where product_id = %s
    """, (prod.get_product_id(),))
    assert dbcursor.fetchall()[0]['count'] == 1
