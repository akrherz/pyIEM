"""Make sure our METAR parsing works!"""
from __future__ import print_function

import pytest
import psycopg2.extras
from pyiem.reference import TRACE_VALUE
from pyiem.nws.products import metarcollect
from pyiem.util import get_dbconn, utc, get_test_file

PARSER = metarcollect.parser
NWSLI_PROVIDER = {
    'CYYE': dict(network='CA_BC_ASOS'),
    'SPS': dict(wfo='OUN'),
    'MIA': dict(wfo='MIA'),
    'ALO': dict(wfo='DSM'),
    'EST': dict(wfo='EST'),
    }
metarcollect.JABBER_SITES = {
    'KALO': None
    }


@pytest.fixture
def dbcursor():
    """Return a disposable database cursor."""
    pgconn = get_dbconn('iem')
    return pgconn.cursor(
        cursor_factory=psycopg2.extras.DictCursor
    )


def test_issue89_peakwind(dbcursor):
    """Are we roundtripping peak wind."""
    code = (
        'KALO 010001Z AUTO 17027G37KT 10SM FEW030 SCT110 19/16 A2979 RMK AO2 '
        'PK WND 18049/2025 RAE48 SLP088 P0005 60014 T01890156 58046'
    )
    mtr = metarcollect.METARReport(code, year=2017, month=1)
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert iemob.data['peak_wind_time'] == utc(2016, 12, 31, 20, 25)


def test_190118_ice(dbcursor):
    """Process a ICE Report."""
    mtr = metarcollect.METARReport(
        ("KABI 031752Z 30010KT 6SM BR FEW009 OVC036 02/01 A3003 RMK AO2 "
         "SLP176 60001 I1000 T00170006 10017 21006 56017")
    )
    assert mtr.ice_accretion_1hr is not None
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert iemob.data['ice_accretion_1hr'] == TRACE_VALUE


def test_180604_nonascii():
    """See that we don't error on non-ASCII METARs"""
    utcnow = utc(2018, 6, 4)
    prod = PARSER(get_test_file("METAR/badchars.txt"), utcnow=utcnow)
    assert len(prod.metars) == 3


def test_future():
    """Can we handle products that are around the first"""
    utcnow = utc(2017, 12, 1)
    prod = PARSER(get_test_file("METAR/first.txt"), utcnow=utcnow)
    assert len(prod.metars) == 2
    assert prod.metars[0].time.month == 11
    assert prod.metars[1].time.month == 12


def test_180201_unparsed():
    """For some reason, this collective was not parsed?!?!"""
    utcnow = utc(2018, 2, 1, 0)
    prod = PARSER(
        get_test_file("METAR/collective2.txt"), utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER)
    assert len(prod.metars) == 35
    assert prod.metars[0].time.month == 1


def test_170824_sa_format():
    """Don't be so noisey when we encounter SA formatted products"""
    utcnow = utc(2017, 8, 24, 14)
    prod = PARSER(
        get_test_file("METAR/sa.txt"), utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER)
    assert not prod.metars


def test_170809_nocrcrlf():
    """Product fails WMO parsing due to usage of RTD as bbb field"""
    utcnow = utc(2017, 8, 9, 9)
    prod = PARSER(
        get_test_file("METAR/rtd_bbb.txt"), utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER)
    assert len(prod.metars) == 1


def test_metarreport(dbcursor):
    """Can we do things with the METARReport"""
    utcnow = utc(2013, 8, 8, 12, 53)
    mtr = metarcollect.METARReport(
        ('SPECI CYYE 081253Z 01060KT 1/4SM FG SKC 10/10 A3006 RMK P0000 '
         'FG6 SLP188=')
    )
    assert mtr.wind_gust is None
    mtr.time = utcnow
    mtr.iemid = 'CYYE'
    mtr.network = 'CA_BC_ASOS'
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert iemob.data['station'] == 'CYYE'
    assert iemob.data['phour'] == TRACE_VALUE
    assert mtr.wind_message() == "gust of 0 knots (0.0 mph) from N @ 1253Z"
    # can we round trip the gust
    iemob.load(dbcursor)
    assert iemob.data['gust'] is None


def test_basic(dbcursor):
    """Simple tests"""
    utcnow = utc(2013, 8, 8, 14)
    prod = PARSER(
        get_test_file("METAR/collective.txt"), utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER
    )
    assert not prod.warnings
    assert len(prod.metars) == 11
    jmsgs = prod.get_jabbers()
    assert len(jmsgs) == 6
    ans = (
        'None,None (SPS) ASOS reports Hail -- KSPS 081352Z 10015KT 10SM '
        'TSGRRA BKN022CB BKN050 BKN200 25/16 A2967 RMK AO2 TSB38RAB25GRB49 '
        'SLP036 LTGICCCCG OHD TS OHD GR 1/3 P0000 T02500161'
    )
    assert jmsgs[0][2]['twitter'] == ans

    iemob, _ = prod.metars[1].to_iemaccess(dbcursor)
    assert abs(iemob.data['phour'] - 0.46) < 0.01
