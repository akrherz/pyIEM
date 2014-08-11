import unittest
import os
import datetime
import pytz

from pyiem.nws.products.sigmet import parser 

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour, minute).replace(
                        tzinfo=pytz.timezone("UTC"))

class TestObservation(unittest.TestCase):
   
    def test_sigaoa(self):
        """ See about parsing 50E properly """
        utcnow = utc(2014, 8, 11, 19, 15)
        tp = parser( get_file('SIGA0A.txt'), utcnow)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 24.35, 2)
   
    def test_sigaob(self):
        """ See about parsing 50E properly """
        utcnow = utc(2014, 8, 11, 19, 15)
        tp = parser( get_file('SIGA0B.txt'), utcnow)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 2.15, 2)
    
    def test_50e(self):
        """ See about parsing 50E properly """
        utcnow = utc(2014, 8, 11, 18, 55)
        ugc_provider = {}
        nwsli_provider= {
            "ASP": dict(lon=-83.39, lat=44.45),
            "ECK": dict(lon=-82.72, lat=43.26),
            "GRR": dict(lon=-85.50, lat=42.79),
        }
            
        tp = parser( get_file('SIGE3.txt'), utcnow, ugc_provider, nwsli_provider )
        #tp.draw()
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 2.15, 2)
    
    def test_sigc(self):
        """ See about parsing SIGC """
        utcnow = utc(2014, 8, 11, 16, 55)
        ugc_provider = {}
        nwsli_provider= {}
        for sid in ("MSL,SJI,MLU,LIT,BTR,LEV,LCH,IAH,YQT,SAW,SAT,DYC,AXC,"
                    +"ODI,DEN,TBE,ADM,JCT,INK,ELP").split(","):
            nwsli_provider[sid] = dict(lon=-99, lat=45)
            
        tp = parser( get_file('SIGC.txt'), utcnow, ugc_provider, nwsli_provider )
        #tp.draw()
        j = tp.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(tp.sigmets[0].ets, utc(2014, 8, 11, 18, 55))
        self.assertEquals(j[0][0], ('KKCI issues SIGMET 62C for AL MS LA AR '
                                    +'till 1855 UTC'))
        self.assertEquals(j[1][0], ('KKCI issues SIGMET 63C for LA TX AND MS '
                                    +'LA TX CSTL WTRS till 1855 UTC'))
    
    def test_sigpat(self):
        """ Make sure we don't have another failure with geom parsing """
        utcnow = utc(2014, 8, 11, 12, 34)
        tp = parser( get_file('SIGPAT.txt'), utcnow )
        j = tp.get_jabbers('http://localhost', 'http://localhost')
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 33.71, 2)
        self.assertEquals(tp.sigmets[0].sts, utc(2014, 8, 11, 12, 35))
        self.assertEquals(tp.sigmets[0].ets, utc(2014, 8, 11, 16, 35))
        self.assertEquals(j[0][0], 'PHFO issues SIGMET TANGO 1 till 1635 UTC')