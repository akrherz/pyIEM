import unittest
import datetime
import os

import pytz

from pyiem.nws import product, ugc
from pyiem.nws.product import TextProductException

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestProduct(unittest.TestCase):

    def test_nomnd_with_timestamp(self):
        ''' Make sure we process timestamps correctly when there is no MND'''
        utcnow = datetime.datetime(2013,12,31,18,0)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct( 
                        get_file('MAVWC0.txt'),
                        utcnow = utcnow)
        ts = datetime.datetime(2014,1,1,0,0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(tp.valid, ts)

    def test_empty(self):
        """ see what happens when we send a blank string """
        self.assertRaises(TextProductException, product.TextProduct, "")

    def test_invalid_mnd_date(self):
        """ Check parsing of timestamp  """
        answer = datetime.datetime(2013,1,3,6,16)
        answer = answer.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct( get_file('CLINYC.txt') )
        self.assertEqual(tp.valid, answer)

    def test_ugc_error130214(self):
        """ Check parsing of SPSJAX  """
        tp = product.TextProduct( get_file('SPSJAX.txt') )
        self.assertEqual(tp.segments[0].ugcs, [ugc.UGC("FL", "Z", 23),
                                               ugc.UGC("FL", "Z", 25),
                                               ugc.UGC("FL", "Z", 30),
                                               ugc.UGC("FL", "Z", 31),
                                               ugc.UGC("FL", "Z", 32)
                                               ])
    def test_no_ugc(self):
        """ Product that does not have UGC encoding """
        data = get_file('CCFMOB.txt')
        tp = product.TextProduct( data )
        self.assertEqual(len(tp.segments[0].ugcs), 0 )

    def test_ugc_invalid_coding(self):
        """ UGC code regression """
        data = get_file('FLW_badugc.txt')
        tp = product.TextProduct( data )
        #self.assertRaises(ugc.UGCParseException, product.TextProduct, data )
        self.assertEqual(len(tp.segments[0].ugcs), 0 )

    def test_000000_ugctime(self):
        """ When there is 000000 as UGC expiration time """
        tp = product.TextProduct( get_file('RECFGZ.txt') )
        self.assertEqual(tp.segments[0].ugcexpire, None)

    def test_stray_space_in_ugc(self):
        """ When there are stray spaces in the UGC! """
        tp = product.TextProduct( get_file('RVDCTP.txt') )
        self.assertEqual(len(tp.segments[0].ugcs), 28)

    def test_ugc_in_hwo(self):
        """ Parse UGC codes in a HWO """
        tp = product.TextProduct( get_file('HWO.txt') )
        self.assertEqual(tp.segments[1].ugcs, [ugc.UGC("LM", "Z", 740),
                                               ugc.UGC("LM", "Z", 741),
                                               ugc.UGC("LM", "Z", 742),
                                               ugc.UGC("LM", "Z", 743),
                                               ugc.UGC("LM", "Z", 744),
                                               ugc.UGC("LM", "Z", 745)
                                               ])

    def test_afos(self):
        """ check AFOS PIL Parsing """
        tp = product.TextProduct( get_file('AFD.txt') )
        self.assertEqual(tp.afos, 'AFDBOX')

    def test_source(self):
        """ check tp.source Parsing """
        tp = product.TextProduct( get_file('AFD.txt') )
        self.assertEqual(tp.source, 'KBOX')

    def test_wmo(self):
        """ check tp.wmo Parsing """
        tp = product.TextProduct( get_file('AFD.txt') )
        self.assertEqual(tp.wmo, 'FXUS61')

    def test_notml(self):
        """ check TOR without TIME...MOT...LOC """
        tp = product.TextProduct( get_file('TOR.txt') )
        self.assertEqual(tp.segments[0].tml_dir, None)

    def test_signature(self):
        """ check svs_search """
        tp = product.TextProduct(get_file('TOR.txt') )
        self.assertEqual(tp.get_signature(), "CBD")               

    def test_spanishMWW(self):
        """ check spanish MWW does not break things """
        tp = product.TextProduct( get_file('MWWspanish.txt') )
        self.assertEqual(tp.z, None)    

    def test_svs_search(self):
        """ check svs_search """
        tp = product.TextProduct( get_file('TOR.txt') )
        self.assertEqual(tp.segments[0].svs_search(), "* AT 1150 AM CDT...THE NATIONAL WEATHER SERVICE HAS ISSUED A TORNADO WARNING FOR DESTRUCTIVE WINDS OVER 110 MPH IN THE EYE WALL AND INNER RAIN BANDS OF HURRICANE KATRINA. THESE WINDS WILL OVERSPREAD MARION...FORREST AND LAMAR COUNTIES DURING THE WARNING PERIOD.")

    def test_product_id(self):
        """ check valid Parsing """
        tp = product.TextProduct( get_file('AFD.txt') )
        self.assertEqual(tp.get_product_id(), "201211270001-KBOX-FXUS61-AFDBOX")
        
    def test_valid(self):
        """ check valid Parsing """
        tp = product.TextProduct( get_file('AFD.txt') )
        ts = datetime.datetime(2012,11,27,0,1)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(tp.valid, ts)

    def test_FFA(self):
        """ check FFA Parsing """
        tp = product.TextProduct( get_file('FFA.txt') )
        self.assertEqual(tp.segments[0].get_hvtec_nwsli(), "NWYI3")

    def test_valid_nomnd(self):
        """ check valid (no Mass News) Parsing """
        utcnow = datetime.datetime(2012,11,27,0,0)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct( 
                        get_file('AFD_noMND.txt'),
                        utcnow = utcnow)
        ts = datetime.datetime(2012,11,27,0,1)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(tp.valid, ts)

    def test_headlines(self):
        """ check headlines Parsing """
        tp = product.TextProduct( 
                        get_file('AFDDMX.txt') )
        self.assertEqual(tp.segments[0].headlines,
                         ['UPDATED FOR 18Z AVIATION DISCUSSION',
                          'Bogus second line with a new line'])
    
    def test_tml(self):
        """ Test TIME...MOT...LOC parsing """
        ts = datetime.datetime(2012, 5, 31, 23, 10)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct( 
                        get_file('SVRBMX.txt') )
        self.assertEqual(tp.segments[0].tml_dir, 238)
        self.assertEqual(tp.segments[0].tml_valid, ts)
        self.assertEqual(tp.segments[0].tml_sknt, 39)
        self.assertEqual(tp.segments[0].tml_giswkt, 
                         'SRID=4326;POINT(-88.53 32.21)')
  
    def test_bullets(self):
        """ Test bullets parsing """
        tp = product.TextProduct( 
                        get_file('TORtag.txt') )
        self.assertEqual( len(tp.segments[0].bullets), 4)
        self.assertEqual( tp.segments[0].bullets[3], "LOCATIONS IMPACTED INCLUDE... MARYSVILLE...LOVILIA...HAMILTON AND BUSSEY.")
    
        tp = product.TextProduct( 
                        get_file('FLSDMX.txt') )
        self.assertEqual( len(tp.segments[2].bullets), 7)
        self.assertEqual( tp.segments[2].bullets[6], "IMPACT...AT 35.5 FEET...WATER AFFECTS 285TH AVENUE NEAR SEDAN BOTTOMS...OR JUST EAST OF THE INTERSECTION OF 285TH AVENUE AND 570TH STREET.")
    
    def test_tags(self):
        """ Test tags parsing """
        tp = product.TextProduct( 
                        get_file('TORtag.txt') )
        self.assertEqual(tp.segments[0].tornadotag, "OBSERVED")
        self.assertEqual(tp.segments[0].tornadodamagetag, "SIGNIFICANT")       
        
    def test_longitude_processing(self):
        ''' Make sure that parsed longitude values are negative! '''
        tp = product.TextProduct( get_file('SVRBMX.txt') )
        self.assertAlmostEqual(tp.segments[0].sbw.exterior.xy[0][0], -88.39, 2)
        
    def test_giswkt(self):
        """ Test giswkt parsing """
        tp = product.TextProduct( get_file('SVRBMX.txt') )
        self.assertAlmostEqual(tp.segments[0].sbw.area, 0.16, 2)
        
        self.assertEqual(tp.segments[0].giswkt, "SRID=4326;MULTIPOLYGON (((-88.3900000000000006 32.5900000000000034, -88.1299999999999955 32.7599999999999980, -88.0799999999999983 32.7199999999999989, -88.1099999999999994 32.6899999999999977, -88.0400000000000063 32.6899999999999977, -88.0600000000000023 32.6400000000000006, -88.0799999999999983 32.6400000000000006, -88.0600000000000023 32.5900000000000034, -87.9300000000000068 32.6300000000000026, -87.8700000000000045 32.5700000000000003, -87.8599999999999994 32.5200000000000031, -87.9200000000000017 32.5200000000000031, -87.9599999999999937 32.4699999999999989, -88.0300000000000011 32.4299999999999997, -88.0499999999999972 32.3699999999999974, -87.9699999999999989 32.3500000000000014, -87.9399999999999977 32.3100000000000023, -88.4099999999999966 32.3100000000000023, -88.3900000000000006 32.5900000000000034)))")
        
if __name__ == '__main__':
    unittest.main()