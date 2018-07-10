"""SPS Parsing"""
import os

from psycopg2.extras import RealDictCursor
from pyiem.util import get_dbconn
from pyiem.nws.ugc import UGC
from pyiem.nws.products.sps import parser as spsparser


def get_transaction():
    """Get a cursor we can use"""
    pgconn = get_dbconn('postgis')
    return pgconn.cursor(cursor_factory=RealDictCursor)


def get_file(name):
    """Helper function to get the text file contents"""
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


def test_sps():
    """Can we parse a SPS properly, yes we can!"""
    txn = get_transaction()
    ugc_provider = {'ALZ039': UGC("AL", "Z", "039", name='Marengo')}
    prod = spsparser(get_file('SPSBMX.txt'), ugc_provider=ugc_provider)
    jmsgs = prod.get_jabbers('http://localhost')
    assert len(prod.segments) == 2
    assert len(jmsgs) == 1
    expected = ("<p>BMX issues <a href='http://localhost?pid=201805292152-"
                "KBMX-WWUS84-SPSBMX'>SIGNIFICANT WEATHER ADVISORY FOR "
                "SOUTHWESTERN MARENGO COUNTY UNTIL 515 PM CDT</a></p>")
    assert jmsgs[0][1] == expected
    assert 'SPSBMX' in jmsgs[0][2]['channels']
    assert 'SPS...' in jmsgs[0][2]['channels']

    prod.sql(txn)
    txn.execute("""
        SELECT count(*) from text_products where product_id = %s
    """, (prod.get_product_id(),))
    assert txn.fetchall()[0]['count'] == 1
