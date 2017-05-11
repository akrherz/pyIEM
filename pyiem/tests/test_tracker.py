import unittest
import psycopg2
import datetime
import pytz
from pyiem.tracker import TrackerEngine, loadqc
from pyiem.network import Table as NetworkTable


class TrackerTests(unittest.TestCase):

    def setUp(self):
        ''' This is called for each test, beware '''
        self.POSTGIS = psycopg2.connect(database='portfolio', host='iemdb')
        self.pcursor = self.POSTGIS.cursor()
        self.IEM = psycopg2.connect(database='iem', host='iemdb')
        self.icursor = self.IEM.cursor()

    def tearDown(self):
        ''' This is called after each test, beware '''
        self.POSTGIS.rollback()
        self.POSTGIS.close()
        self.IEM.rollback()
        self.IEM.close()

    def test_loadqc(self):
        """Make sure we exercise the loadqc stuff"""
        q = loadqc()
        self.assertEquals(len(q), 0)
        q = loadqc(cursor=self.pcursor)
        self.assertEquals(len(q), 0)
        self.pcursor.execute("""
            INSERT into tt_base(s_mid, sensor, status) VALUES
            ('BOGUS', 'tmpf', 'OPEN')
        """)
        q = loadqc(cursor=self.pcursor)
        self.assertEquals(len(q), 1)

    def test_workflow(self):
        """ Test that we can do stuff! """
        sid1 = 'XXX'
        sid2 = 'YYY'
        pnetwork = 'xxxxxx'
        nt = NetworkTable(None)
        nt.sts[sid1] = dict(name='XXX Site Name', network='IA_XXXX',
                            tzname='America/Chicago')
        nt.sts[sid2] = dict(name='YYY Site Name', network='IA_XXXX',
                            tzname='America/Chicago')
        valid = datetime.datetime.utcnow()
        valid = valid.replace(tzinfo=pytz.timezone("UTC"))
        threshold = valid - datetime.timedelta(hours=3)
        obs = {sid1: {'valid': valid},
               sid2: {'valid': valid - datetime.timedelta(hours=6)}}
        # Create dummy iem_site_contacts
        self.pcursor.execute("""INSERT into iem_site_contacts
            (portfolio, s_mid, email) VALUES (%s, %s, %s)
            """, (pnetwork, sid1, 'akrherz@localhost'))
        self.pcursor.execute("""INSERT into iem_site_contacts
            (portfolio, s_mid, email) VALUES (%s, %s, %s)
            """, (pnetwork, sid2, 'root@localhost'))
        # Create some dummy tickets
        self.pcursor.execute("""INSERT into tt_base (portfolio, s_mid, subject,
        status, author) VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                             (pnetwork, sid1, 'FIXME PLEASE OPEN', 'OPEN',
                              'mesonet'))
        self.pcursor.execute("""INSERT into tt_base (portfolio, s_mid, subject,
        status, author) VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                             (pnetwork, sid1, 'FIXME PLEASE CLOSED', 'CLOSED',
                              'mesonet'))
        tracker = TrackerEngine(self.icursor, self.pcursor)
        tracker.process_network(obs, pnetwork, nt, threshold)
        tracker.send_emails(really_send=False)
        self.assertEquals(len(tracker.emails), 1)

        tracker.emails = {}
        obs[sid1]['valid'] = valid - datetime.timedelta(hours=6)
        obs[sid2]['valid'] = valid
        tracker.process_network(obs, pnetwork, nt, threshold)
        tracker.send_emails(really_send=False)
        self.assertEquals(len(tracker.emails), 2)

        tracker.emails = {}
        obs[sid1]['valid'] = valid - datetime.timedelta(hours=6)
        obs[sid2]['valid'] = valid
        tracker.process_network(obs, pnetwork, nt, threshold)
        tracker.send_emails(really_send=False)
        self.assertEquals(len(tracker.emails), 0)
