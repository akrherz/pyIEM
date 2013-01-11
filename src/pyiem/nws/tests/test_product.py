import unittest
import datetime

from pyiem import iemtz
from pyiem.nws import product, ugc

class TestObservation(unittest.TestCase):

    def test_000000_ugctime(self):
        """ When there is 000000 as UGC expiration time """
        tp = product.TextProduct( open('data/product_examples/RECFGZ.txt').read())
        self.assertEqual(tp.segments[0].ugcexpire, None)

    def test_stray_space_in_ugc(self):
        """ When there are stray spaces in the UGC! """
        tp = product.TextProduct( open('data/product_examples/RVDCTP.txt').read())
        self.assertEqual(len(tp.segments[0].ugcs), 28)

    def test_ugc_in_hwo(self):
        """ Parse UGC codes in a HWO """
        tp = product.TextProduct( open('data/product_examples/HWO.txt').read())
        self.assertEqual(tp.segments[1].ugcs, [ugc.UGC("LM", "Z", 740),
                                               ugc.UGC("LM", "Z", 741),
                                               ugc.UGC("LM", "Z", 742),
                                               ugc.UGC("LM", "Z", 743),
                                               ugc.UGC("LM", "Z", 744),
                                               ugc.UGC("LM", "Z", 745)
                                               ])

    def test_afos(self):
        """ check AFOS PIL Parsing """
        tp = product.TextProduct( open('data/product_examples/AFD.txt').read())
        self.assertEqual(tp.afos, 'AFDBOX')

    def test_source(self):
        """ check tp.source Parsing """
        tp = product.TextProduct( open('data/product_examples/AFD.txt').read())
        self.assertEqual(tp.source, 'KBOX')

    def test_wmo(self):
        """ check tp.wmo Parsing """
        tp = product.TextProduct( open('data/product_examples/AFD.txt').read())
        self.assertEqual(tp.wmo, 'FXUS61')

    def test_notml(self):
        """ check TOR without TIME...MOT...LOC """
        tp = product.TextProduct( open('data/product_examples/TOR.txt').read())
        self.assertEqual(tp.segments[0].tml_dir, None)

    def test_signature(self):
        """ check svs_search """
        tp = product.TextProduct( open('data/product_examples/TOR.txt').read())
        self.assertEqual(tp.get_signature(), "CBD")               

    def test_spanishMWW(self):
        """ check spanish MWW does not break things """
        tp = product.TextProduct( open('data/product_examples/MWWspanish.txt').read())
        self.assertEqual(tp.z, None)    

    def test_svs_search(self):
        """ check svs_search """
        tp = product.TextProduct( open('data/product_examples/TOR.txt').read())
        self.assertEqual(tp.segments[0].svs_search(), "* AT 1150 AM CDT...THE NATIONAL WEATHER SERVICE HAS ISSUED A TORNADO WARNING FOR DESTRUCTIVE WINDS OVER 110 MPH IN THE EYE WALL AND INNER RAIN BANDS OF HURRICANE KATRINA. THESE WINDS WILL OVERSPREAD MARION...FORREST AND LAMAR COUNTIES DURING THE WARNING PERIOD.")

    def test_product_id(self):
        """ check valid Parsing """
        tp = product.TextProduct( open('data/product_examples/AFD.txt').read())
        self.assertEqual(tp.get_product_id(), "201211270001-KBOX-FXUS61-AFDBOX")
        
    def test_valid(self):
        """ check valid Parsing """
        tp = product.TextProduct( open('data/product_examples/AFD.txt').read())
        ts = datetime.datetime(2012,11,27,0,1)
        ts = ts.replace(tzinfo=iemtz.UTC())
        self.assertEqual(tp.valid, ts)

    def test_FFA(self):
        """ check FFA Parsing """
        tp = product.TextProduct( open('data/product_examples/FFA.txt').read())
        self.assertEqual(tp.segments[0].get_hvtec_nwsli(), "NWYI3")

    def test_valid_nomnd(self):
        """ check valid (no Mass News) Parsing """
        utcnow = datetime.datetime(2012,11,27,0,0)
        utcnow = utcnow.replace(tzinfo=iemtz.UTC())
        tp = product.TextProduct( 
                        open('data/product_examples/AFD_noMND.txt').read(),
                        utcnow = utcnow)
        ts = datetime.datetime(2012,11,27,0,1)
        ts = ts.replace(tzinfo=iemtz.UTC())
        self.assertEqual(tp.valid, ts)

    def test_headlines(self):
        """ check headlines Parsing """
        tp = product.TextProduct( 
                        open('data/product_examples/AFDDMX.txt').read())
        self.assertEqual(tp.segments[0].headlines,
                         ['UPDATED FOR 18Z AVIATION DISCUSSION',
                          'Bogus second line with a new line'])
    
    def test_tml(self):
        """ Test TIME...MOT...LOC parsing """
        ts = datetime.datetime(2012, 5, 31, 23, 10)
        ts = ts.replace(tzinfo=iemtz.UTC())
        tp = product.TextProduct( 
                        open('data/product_examples/SVRBMX.txt').read())
        self.assertEqual(tp.segments[0].tml_dir, 238)
        self.assertEqual(tp.segments[0].tml_valid, ts)
        self.assertEqual(tp.segments[0].tml_sknt, 39)
        self.assertEqual(tp.segments[0].tml_giswkt, 
                         'SRID=4326;POINT(-88.53 32.21)')
  
    def test_bullets(self):
        """ Test bullets parsing """
        tp = product.TextProduct( 
                        open('data/product_examples/TORtag.txt').read())
        self.assertEqual( len(tp.segments[0].bullets), 4)
        self.assertEqual( tp.segments[0].bullets[3], "LOCATIONS IMPACTED INCLUDE... MARYSVILLE...LOVILIA...HAMILTON AND BUSSEY.")
    
    def test_tags(self):
        """ Test tags parsing """
        tp = product.TextProduct( 
                        open('data/product_examples/TORtag.txt').read())
        self.assertEqual(tp.segments[0].tornadotag, "OBSERVED")
        self.assertEqual(tp.segments[0].tornadodamagetag, "SIGNIFICANT")       
        
    def test_giswkt(self):
        """ Test giswkt parsing """
        tp = product.TextProduct( 
                        open('data/product_examples/SVRBMX.txt').read())
        self.assertEqual(tp.segments[0].giswkt, 
                         'SRID=4326;MULTIPOLYGON(((-88.39 32.59,-88.13 32.76,-88.08 32.72,-88.11 32.69,-88.04 32.69,-88.06 32.64,-88.08 32.64,-88.06 32.59,-87.93 32.63,-87.87 32.57,-87.86 32.52,-87.92 32.52,-87.96 32.47,-88.03 32.43,-88.05 32.37,-87.97 32.35,-87.94 32.31,-88.41 32.31,-88.39 32.59)))')
if __name__ == '__main__':
    unittest.main()