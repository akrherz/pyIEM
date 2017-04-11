import unittest
import datetime
import os

import pytz

from pyiem.nws import product, ugc
from pyiem.nws.product import WMO_RE
from pyiem.nws.product import TextProductException
from pyiem.nws.products import parser as productparser


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour,
                             minute).replace(tzinfo=pytz.timezone("UTC"))


class TestProduct(unittest.TestCase):

    def test_170411_fakemnd(self):
        """This RTP has a quasi-faked timestamp in the header causing error"""
        tp = productparser(get_file('RTPSGX.txt'))
        res = utc(2017, 4, 10, 23, 30)
        self.assertEqual(tp.valid, res)

    def test_151024_cae(self):
        """Make sure this CAE product works and does not throw an UGC error"""
        tp = productparser(get_file('CAEIA.txt'))
        self.assertEquals(tp.afos, 'CAEIA')

    def test_resent(self):
        """ Make sure we can tell a ...RESENT product """
        tp = productparser(get_file('MWWBRO.txt'))
        self.assertTrue(tp.is_resent())

    def test_wmoheader(self):
        """" Make sure we can handle some header variations """
        ar = ["FTUS43 KOAX 102320    ",
              "FTUS43 KOAX 102320  COR ",
              "FTUS43 KOAX 102320  COR  ",
              "FTUS43 KOAX 102320",
              ]
        for a in ar:
            self.assertTrue(WMO_RE.match(a) is not None)

    def test_RFD(self):
        """ Parse a RFD """
        tp = productparser(get_file('RFDOAX.txt'))
        self.assertEqual(tp.get_channels()[0], 'RFDOAX')
        j = tp.get_jabbers('http://localhost')
        self.assertEqual(j[0][0], (
             'OAX issues Grassland Fire Danger '
             '(RFD) http://localhost?pid=201501191010-KOAX-FNUS63-RFDOAX'))

    def test_HWO(self):
        """ Parse a HWO """
        tp = productparser(get_file('HWO.txt'))
        self.assertEqual(tp.get_channels()[0], 'HWOLOT')
        j = tp.get_jabbers('http://localhost')
        self.assertEqual(j[0][0], (
            'LOT issues Hazardous Weather Outlook '
            '(HWO) http://localhost?pid=201301082123-KLOT-FLUS43-HWOLOT'))

    def test_140710_wmoheader_fail(self):
        """ Make sure COR in WMO header does not trip us up"""
        tp = product.TextProduct(get_file('MANANN.txt'))
        self.assertEqual(tp.afos, 'MANANN')
        self.assertTrue(tp.is_correction())

    def test_now_jabber(self):
        ''' See if we can process a NOW and get the jabber result '''
        tp = product.TextProduct(get_file('NOWDMX.txt'))
        j = tp.get_jabbers("http://localhost")
        self.assertEqual(j[0][0],
                         ("DMX issues Short-term Forecast (NOW) "
                          "http://localhost?"
                          "pid=201003041442-KDMX-FPUS73-NOWDMX"))

    def test_nomnd_with_timestamp(self):
        ''' Make sure we process timestamps correctly when there is no MND'''
        utcnow = datetime.datetime(2013, 12, 31, 18, 0)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct(get_file('MAVWC0.txt'), utcnow=utcnow)
        ts = datetime.datetime(2014, 1, 1, 0, 0)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(tp.valid, ts)

    def test_empty(self):
        """ see what happens when we send a blank string """
        self.assertRaises(TextProductException, product.TextProduct, "")

    def test_invalid_mnd_date(self):
        """ Check parsing of timestamp  """
        answer = datetime.datetime(2013, 1, 3, 6, 16)
        answer = answer.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct(get_file('CLI/CLINYC.txt'))
        self.assertEqual(tp.valid, answer)

    def test_ugc_error130214(self):
        """ Check parsing of SPSJAX  """
        tp = product.TextProduct(get_file('SPSJAX.txt'))
        self.assertEqual(tp.segments[0].ugcs, [ugc.UGC("FL", "Z", 23),
                                               ugc.UGC("FL", "Z", 25),
                                               ugc.UGC("FL", "Z", 30),
                                               ugc.UGC("FL", "Z", 31),
                                               ugc.UGC("FL", "Z", 32)
                                               ])

    def test_no_ugc(self):
        """ Product that does not have UGC encoding """
        data = get_file('CCFMOB.txt')
        tp = product.TextProduct(data)
        self.assertEqual(len(tp.segments[0].ugcs), 0)

    def test_ugc_invalid_coding(self):
        """ UGC code regression """
        data = get_file('FLW_badugc.txt')
        tp = product.TextProduct(data)
        # self.assertRaises(ugc.UGCParseException, product.TextProduct, data )
        self.assertEqual(len(tp.segments[0].ugcs), 0)

    def test_000000_ugctime(self):
        """ When there is 000000 as UGC expiration time """
        tp = product.TextProduct(get_file('RECFGZ.txt'))
        self.assertEqual(tp.segments[0].ugcexpire, None)

    def test_stray_space_in_ugc(self):
        """ When there are stray spaces in the UGC! """
        tp = product.TextProduct(get_file('RVDCTP.txt'))
        self.assertEqual(len(tp.segments[0].ugcs), 28)

    def test_ugc_in_hwo(self):
        """ Parse UGC codes in a HWO """
        tp = product.TextProduct(get_file('HWO.txt'))
        self.assertEqual(tp.segments[1].ugcs, [ugc.UGC("LM", "Z", 740),
                                               ugc.UGC("LM", "Z", 741),
                                               ugc.UGC("LM", "Z", 742),
                                               ugc.UGC("LM", "Z", 743),
                                               ugc.UGC("LM", "Z", 744),
                                               ugc.UGC("LM", "Z", 745)
                                               ])

    def test_afos(self):
        """ check AFOS PIL Parsing """
        tp = product.TextProduct(get_file('AFD.txt'))
        self.assertEqual(tp.afos, 'AFDBOX')

    def test_source(self):
        """ check tp.source Parsing """
        tp = product.TextProduct(get_file('AFD.txt'))
        self.assertEqual(tp.source, 'KBOX')

    def test_wmo(self):
        """ check tp.wmo Parsing """
        tp = product.TextProduct(get_file('AFD.txt'))
        self.assertEqual(tp.wmo, 'FXUS61')

    def test_notml(self):
        """ check TOR without TIME...MOT...LOC """
        tp = product.TextProduct(get_file('TOR.txt'))
        self.assertEqual(tp.segments[0].tml_dir, None)

    def test_signature(self):
        """ check svs_search """
        tp = product.TextProduct(get_file('TOR.txt'))
        self.assertEqual(tp.get_signature(), "CBD")

    def test_spanishMWW(self):
        """ check spanish MWW does not break things """
        tp = product.TextProduct(get_file('MWWspanish.txt'))
        self.assertEqual(tp.z, None)

    def test_svs_search(self):
        """ check svs_search """
        tp = product.TextProduct(get_file('TOR.txt'))
        self.assertEqual(tp.segments[0].svs_search(),
                         ("* AT 1150 AM CDT...THE NATIONAL WEATHER SERVICE "
                          "HAS ISSUED A TORNADO WARNING FOR DESTRUCTIVE "
                          "WINDS OVER 110 MPH IN THE EYE WALL AND INNER RAIN "
                          "BANDS OF HURRICANE KATRINA. THESE WINDS WILL "
                          "OVERSPREAD MARION...FORREST AND LAMAR COUNTIES "
                          "DURING THE WARNING PERIOD."))

    def test_product_id(self):
        """ check valid Parsing """
        tp = product.TextProduct(get_file('AFD.txt'))
        self.assertEqual(tp.get_product_id(),
                         "201211270001-KBOX-FXUS61-AFDBOX")

    def test_valid(self):
        """ check valid Parsing """
        tp = product.TextProduct(get_file('AFD.txt'))
        ts = datetime.datetime(2012, 11, 27, 0, 1)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(tp.valid, ts)

    def test_FFA(self):
        """ check FFA Parsing """
        tp = product.TextProduct(get_file('FFA.txt'))
        self.assertEqual(tp.segments[0].get_hvtec_nwsli(), "NWYI3")

    def test_valid_nomnd(self):
        """ check valid (no Mass News) Parsing """
        utcnow = datetime.datetime(2012, 11, 27, 0, 0)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct(get_file('AFD_noMND.txt'),
                                 utcnow=utcnow)
        ts = datetime.datetime(2012, 11, 27, 0, 1)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(tp.valid, ts)

    def test_headlines(self):
        """ check headlines Parsing """
        tp = product.TextProduct(get_file('AFDDMX.txt'))
        self.assertEqual(tp.segments[0].headlines,
                         ['UPDATED FOR 18Z AVIATION DISCUSSION',
                          'Bogus second line with a new line'])

    def test_tml(self):
        """ Test TIME...MOT...LOC parsing """
        ts = datetime.datetime(2012, 5, 31, 23, 10)
        ts = ts.replace(tzinfo=pytz.timezone("UTC"))
        tp = product.TextProduct(get_file('SVRBMX.txt'))
        self.assertEqual(tp.segments[0].tml_dir, 238)
        self.assertEqual(tp.segments[0].tml_valid, ts)
        self.assertEqual(tp.segments[0].tml_sknt, 39)
        self.assertEqual(tp.segments[0].tml_giswkt,
                         'SRID=4326;POINT(-88.53 32.21)')

    def test_bullets(self):
        """ Test bullets parsing """
        tp = product.TextProduct(get_file('TORtag.txt'))
        self.assertEqual(len(tp.segments[0].bullets), 4)
        self.assertEqual(tp.segments[0].bullets[3],
                         ("LOCATIONS IMPACTED INCLUDE... MARYSVILLE...LOVILIA"
                          "...HAMILTON AND BUSSEY."))

        tp = product.TextProduct(get_file('FLSDMX.txt'))
        self.assertEqual(len(tp.segments[2].bullets), 7)
        self.assertEqual(tp.segments[2].bullets[6],
                         ("IMPACT...AT 35.5 FEET...WATER AFFECTS 285TH "
                          "AVENUE NEAR SEDAN BOTTOMS...OR JUST EAST OF THE "
                          "INTERSECTION OF 285TH AVENUE AND 570TH STREET."))

    def test_tags(self):
        """ Test tags parsing """
        tp = product.TextProduct(get_file('TORtag.txt'))
        self.assertEqual(tp.segments[0].tornadotag, "OBSERVED")
        self.assertEqual(tp.segments[0].tornadodamagetag, "SIGNIFICANT")

    def test_longitude_processing(self):
        ''' Make sure that parsed longitude values are negative! '''
        tp = product.TextProduct(get_file('SVRBMX.txt'))
        self.assertAlmostEqual(tp.segments[0].sbw.exterior.xy[0][0], -88.39, 2)

    def test_giswkt(self):
        """ Test giswkt parsing """
        tp = product.TextProduct(get_file('SVRBMX.txt'))
        self.assertAlmostEqual(tp.segments[0].sbw.area, 0.16, 2)

        self.assertEqual(tp.segments[0].giswkt,
                         ('SRID=4326;MULTIPOLYGON '
                          '(((-88.390000 32.590000, -88.130000 32.760000, '
                          '-88.080000 32.720000, -88.110000 32.690000, '
                          '-88.040000 32.690000, -88.060000 32.640000, '
                          '-88.080000 32.640000, -88.060000 32.590000, '
                          '-87.930000 32.630000, -87.870000 32.570000, '
                          '-87.860000 32.520000, -87.920000 32.520000, '
                          '-87.960000 32.470000, -88.030000 32.430000, '
                          '-88.050000 32.370000, -87.970000 32.350000, '
                          '-87.940000 32.310000, -88.410000 32.310000, '
                          '-88.390000 32.590000)))'))


if __name__ == '__main__':
    unittest.main()
