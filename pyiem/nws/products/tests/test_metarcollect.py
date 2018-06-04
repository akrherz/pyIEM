"""Make sure our METAR parsing works!"""
from __future__ import print_function
import os
import unittest

import psycopg2.extras
from pyiem.reference import TRACE_VALUE
from pyiem.nws.products import metarcollect
from pyiem.util import get_dbconn, utc

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


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/METAR/%s" % (basedir, name)
    return open(fn, 'rb').read().decode('utf-8')


class TestMETAR(unittest.TestCase):
    """ Tests """

    def setUp(self):
        self.conn = get_dbconn('iem')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def test_180604_nonascii(self):
        """See that we don't error on non-ASCII METARs"""
        utcnow = utc(2018, 6, 4)
        prod = PARSER(get_file("badchars.txt"), utcnow=utcnow)
        assert len(prod.metars) == 3

    def test_future(self):
        """Can we handle products that are around the first"""
        utcnow = utc(2017, 12, 1)
        prod = PARSER(get_file("first.txt"), utcnow=utcnow)
        self.assertEquals(len(prod.metars), 2)
        self.assertEquals(prod.metars[0].time.month, 11)
        self.assertEquals(prod.metars[1].time.month, 12)

    def test_180201_unparsed(self):
        """For some reason, this collective was not parsed?!?!"""
        utcnow = utc(2018, 2, 1, 0)
        prod = PARSER(get_file("collective2.txt"), utcnow=utcnow,
                      nwsli_provider=NWSLI_PROVIDER)
        self.assertEquals(len(prod.metars), 35)
        self.assertEquals(prod.metars[0].time.month, 1)

    def test_170824_sa_format(self):
        """Don't be so noisey when we encounter SA formatted products"""
        utcnow = utc(2017, 8, 24, 14)
        prod = PARSER(get_file("sa.txt"), utcnow=utcnow,
                      nwsli_provider=NWSLI_PROVIDER)
        self.assertEquals(len(prod.metars), 0)

    def test_170809_nocrcrlf(self):
        """Product fails WMO parsing due to usage of RTD as bbb field"""
        utcnow = utc(2017, 8, 9, 9)
        prod = PARSER(get_file("rtd_bbb.txt"), utcnow=utcnow,
                      nwsli_provider=NWSLI_PROVIDER)
        self.assertEquals(len(prod.metars), 1)

    def test_metarreport(self):
        """Can we do things with the METARReport"""
        utcnow = utc(2013, 8, 8, 12, 53)
        mtr = metarcollect.METARReport(('SPECI CYYE 081253Z 01060G60KT 1/4SM '
                                        'FG SKC 10/10 A3006 RMK P0000 '
                                        'FG6 SLP188='))
        mtr.time = utcnow
        mtr.iemid = 'CYYE'
        mtr.network = 'CA_BC_ASOS'
        iemob, _ = mtr.to_iemaccess(self.cursor)
        self.assertEqual(iemob.data['station'], 'CYYE')
        self.assertEqual(iemob.data['phour'], TRACE_VALUE)
        self.assertEquals(mtr.wind_message(),
                          "gust of 60 knots (69.1 mph) from N @ 1253Z")

    def test_basic(self):
        """Simple tests"""
        utcnow = utc(2013, 8, 8, 14)
        prod = PARSER(get_file("collective.txt"), utcnow=utcnow,
                      nwsli_provider=NWSLI_PROVIDER)
        self.assertEquals(len(prod.warnings), 0,
                          '\n'.join(prod.warnings))
        self.assertEquals(len(prod.metars), 11)
        jmsgs = prod.get_jabbers()
        self.assertEquals(len(jmsgs), 6)

        iemob, _ = prod.metars[1].to_iemaccess(self.cursor)
        self.assertEqual(iemob.data['phour'], 0.46)
