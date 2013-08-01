import unittest
import os
import psycopg2
import datetime
import pytz

from pyiem.nws.products.mcd import parser as mcdparser
from pyiem.nws.products.lsr import parser as lsrparser
from pyiem.nws.products.vtec import parser as vtecparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestProducts(unittest.TestCase):
    
    def setUp(self):
        self.dbconn = psycopg2.connect(database='postgis')
        self.txn = self.dbconn.cursor()
    
    def tearDown(self):
        self.dbconn.close()
    
    def test_vtec_series(self):
        ''' Test a lifecycle of WSW products '''
        prod = vtecparser( get_file('WSWDMX/WSW_00.txt') )
        self.assertEqual(prod.afos, 'WSWDMX')
        prod.sql( self.txn )
    
        ''' Did Marshall County IAZ049 get a ZR.Y '''
        self.txn.execute("""SELECT issue from warnings_2013 WHERE
        wfo = 'DMX' and eventid = 1 and phenomena = 'ZR' and 
        significance = 'Y' and gtype = 'C' and status = 'EXB'
        and ugc = 'IAZ049' """)
        self.assertEqual( self.txn.rowcount, 1)

        prod = vtecparser( get_file('WSWDMX/WSW_01.txt') )
        self.assertEqual(prod.afos, 'WSWDMX')
        prod.sql( self.txn )
    
        ''' Is IAZ006 in CON status with proper end time '''
        answer = datetime.datetime(2013,1,28,6).replace(
                                                tzinfo=pytz.timezone("UTC"))
        self.txn.execute("""SELECT expire from warnings_2013 WHERE
        wfo = 'DMX' and eventid = 1 and phenomena = 'WS' and 
        significance = 'W' and gtype = 'C' and status = 'CON'
        and ugc = 'IAZ006' """)

        self.assertEqual( self.txn.rowcount, 1)
        row = self.txn.fetchone()
        self.assertEqual( row[0], answer )
 
        # No change
        for i in range(2,9):
            prod = vtecparser( get_file('WSWDMX/WSW_%02i.txt' % (i,)) )
            self.assertEqual(prod.afos, 'WSWDMX')
            prod.sql( self.txn )

        prod = vtecparser( get_file('WSWDMX/WSW_09.txt') )
        self.assertEqual(prod.afos, 'WSWDMX')
        prod.sql( self.txn )

        # IAZ006 should be cancelled
        answer = datetime.datetime(2013,1,28,6).replace(
                                                tzinfo=pytz.timezone("UTC"))
        self.txn.execute("""SELECT expire from warnings_2013 WHERE
        wfo = 'DMX' and eventid = 1 and phenomena = 'WS' and 
        significance = 'W' and gtype = 'C' and status = 'CAN'
        and ugc = 'IAZ006' """)

        self.assertEqual( self.txn.rowcount, 1)
        row = self.txn.fetchone()
        self.assertEqual( row[0], answer )

    
    def test_vtec(self):
        ''' Simple test of VTEC parser '''
        prod = vtecparser( get_file('TOR.txt') )
        self.assertEqual(prod.skip_con, False)
        self.assertAlmostEqual(prod.segments[0].sbw.area, 0.3053, 4)
    
        prod.sql( self.txn )
        
        # See if we got it in the database!
        self.txn.execute("""SELECT issue from warnings_2005 WHERE
        wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and 
        significance = 'W' and gtype = 'C' and status = 'NEW' """)
        self.assertEqual( self.txn.rowcount, 3)

        self.txn.execute("""SELECT issue from sbw_2005 WHERE
        wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and 
        significance = 'W' and status = 'NEW' """)
        self.assertEqual( self.txn.rowcount, 1)

    
    def test_01(self):
        """ process a valid LSR without blemish """
        prod = lsrparser( get_file("LSR.txt") )
        self.assertEqual(len(prod.lsrs), 58)
        
        self.assertAlmostEqual(prod.lsrs[57].magnitude_f, 73, 0)
        self.assertEqual(prod.lsrs[57].county, "Marion")
        self.assertEqual(prod.lsrs[57].state, "IA")
        self.assertAlmostEqual(prod.lsrs[57].get_lon(), -93.11, 2)
        self.assertAlmostEqual(prod.lsrs[57].get_lat(), 41.3, 1)
        
        self.assertEqual(prod.is_summary(), True)
        self.assertEqual(prod.lsrs[57].wfo , 'DMX')
        
        self.assertEqual(prod.lsrs[57].get_jabbers()[0], ("Knoxville Airport "
        +"[Marion Co, IA] AWOS reports NON-TSTM WND GST of 73.00 MPH at 22 "
        +"Jul, 10:55 PM CST -- HEAT BURST. TEMPERATURE ROSE FROM 70 TO 84 "
        +"IN 15 MINUTES AND DEW POINT DROPPED FROM 63 TO 48 IN 10 MINUTES. "
        +"http://localhost"))
        
        self.assertEqual(prod.lsrs[5].tweet(), ("At 4:45 PM, LAW ENFORCEMENT "
                         +"reports TSTM WND DMG #DMX"))
    
    def test_mcdparser(self):
        ''' Test Parsing of MCD Product '''
        prod = mcdparser( get_file('SWOMCD.txt') )
        self.assertAlmostEqual(prod.geometry.area, 4.302, 3)
        self.assertEqual(prod.discussion_num, 1525 )
        self.assertEqual(prod.attn_wfo[2], 'DLH')
        self.assertEqual(prod.areas_affected, ("PORTIONS OF NRN WI AND "
                                               +"THE UPPER PENINSULA OF MI"))
