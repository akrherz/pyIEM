"""Make sure our METAR parsing works!"""
from __future__ import print_function
import os
import unittest
import datetime

import pytz
import psycopg2.extras
from pyiem.nws.products import metarcollect

PARSER = metarcollect.parser
NWSLI_PROVIDER = {
    'CYYE': dict(network='CA_BC_ASOS'),
    'SPS': dict(wfo='OUN'),
    'MIA': dict(wfo='MIA'),
    'ALO': dict(wfo='DSM'),
    'EST': dict(wfo='EST'),
    }


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/METAR/%s" % (basedir, name)
    return open(fn).read()


class TestMETAR(unittest.TestCase):
    """ Tests """

    def setUp(self):
        self.conn = psycopg2.connect(database='iem', host='iemdb')
        self.cursor = self.conn.cursor(
            cursor_factory=psycopg2.extras.DictCursor)

    def test_metarreport(self):
        """Can we do things with the METARReport"""
        mtr = metarcollect.METARReport(('SPECI CYYE 081253Z 01060G60KT 1/4SM '
                                        'FG SKC 10/10 A3006 RMK FG6 SLP188='))
        mtr.iemid = 'CYYE'
        mtr.network = 'CA_BC_ASOS'
        iemob, _ = mtr.to_iemaccess(self.cursor)
        self.assertEqual(iemob.data['station'], 'CYYE')
        self.assertEquals(mtr.wind_message(),
                          "gust of 60 knots (69.1 mph) from N @ 1253Z")

    def test_basic(self):
        """Simple tests"""
        utcnow = datetime.datetime(2017, 8, 8, 14).replace(tzinfo=pytz.utc)
        prod = PARSER(get_file("collective.txt"), utcnow=utcnow,
                      nwsli_provider=NWSLI_PROVIDER)
        self.assertEquals(len(prod.warnings), 0,
                          '\n'.join(prod.warnings))
        self.assertEquals(len(prod.metars), 10)
        jmsgs = prod.get_jabbers()
        self.assertEquals(len(jmsgs), 4)
