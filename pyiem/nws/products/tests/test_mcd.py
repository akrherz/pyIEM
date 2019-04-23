"""MCD/MPD tests."""

import psycopg2.extras
import pytest
from pyiem.nws.products.mcd import parser
from pyiem.util import get_dbconn, utc, get_test_file


@pytest.fixture
def dbcursor():
    """Database cursor."""
    return get_dbconn('postgis').cursor(
        cursor_factory=psycopg2.extras.DictCursor)


def test_170926_nodbinsert(dbcursor):
    """This product never hit the database for some reason?"""
    prod = parser(get_test_file('MCD_MPD/SWOMCD_2010.txt'))
    prod.database_save(dbcursor)
    dbcursor.execute("""
        SELECT * from text_products where product_id = %s
    """, (prod.get_product_id(), ))
    assert dbcursor.rowcount == 1


def test_mpd_mcdparser(dbcursor):
    ''' The mcdparser can do WPC's MPD as well, test it '''
    prod = parser(get_test_file('MCD_MPD/MPD.txt'))
    assert abs(prod.geometry.area - 4.657) < 0.001
    assert prod.attn_wfo == ['PHI', 'AKQ', 'CTP', 'LWX']
    assert prod.attn_rfc == ['MARFC']
    ans = (
        '#WPC issues MPD 98: NRN VA...D.C'
        '....CENTRAL MD INTO SERN PA '
        'http://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php'
        '?md=98&yr=2013')
    assert prod.tweet() == ans
    ans = (
        'Weather Prediction Center issues '
        'Mesoscale Precipitation Discussion #98'
        ' http://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php'
        '?md=98&amp;yr=2013')
    assert prod.get_jabbers('http://localhost')[0][0] == ans
    prod.database_save(dbcursor)


def test_mcdparser(dbcursor):
    ''' Test Parsing of MCD Product '''
    prod = parser(get_test_file('MCD_MPD/SWOMCD.txt'))
    assert abs(prod.geometry.area - 4.302) < 0.001
    assert prod.discussion_num == 1525
    assert prod.attn_wfo[2] == 'DLH'
    ans = "PORTIONS OF NRN WI AND THE UPPER PENINSULA OF MI"
    assert prod.areas_affected == ans

    # With probability this time
    prod = parser(get_test_file('MCD_MPD/SWOMCDprob.txt'))
    assert abs(prod.geometry.area - 2.444) < 0.001
    assert prod.watch_prob == 20

    jmsg = prod.get_jabbers('http://localhost')
    ans = (
        '<p>Storm Prediction Center issues '
        '<a href="http://www.spc.noaa.gov/'
        'products/md/2013/md1678.html">Mesoscale Discussion #1678</a> '
        '[watch probability: 20%] (<a href="http://localhost'
        '?pid=201308091725-KWNS-ACUS11-SWOMCD">View text</a>)</p>')
    assert jmsg[0][1] == ans
    ans = (
        'Storm Prediction Center issues Mesoscale Discussion #1678 '
        '[watch probability: 20%] '
        'http://www.spc.noaa.gov/products/md/2013/md1678.html')
    assert jmsg[0][0] == ans
    ans = utc(2013, 8, 9, 17, 25)
    assert prod.sts == ans
    ans = utc(2013, 8, 9, 19, 30)
    assert prod.ets == ans

    prod.database_save(dbcursor)
