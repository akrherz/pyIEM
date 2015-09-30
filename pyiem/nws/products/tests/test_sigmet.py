import unittest
import os
import datetime
import pytz

from pyiem.nws.products.sigmet import parser, compute_esol


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/SIGMETS/%s" % (basedir, name)
    return open(fn).read()


def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour, minute).replace(
                        tzinfo=pytz.timezone("UTC"))


class TestSIGMET(unittest.TestCase):

    def test_150930_SIGAK2(self):
        """Got an error with this product"""
        utcnow = utc(2015, 9, 30, 16, 56)
        tp = parser(get_file('SIGAK2.txt'), utcnow)
        self.assertEquals(len(tp.sigmets), 0)

    def test_150921_SIGPAS(self):
        """Got an error with this product"""
        utcnow = utc(2015, 9, 21, 10, 57)
        tp = parser(get_file('SIGPAS.txt'), utcnow)
        self.assertEquals(len(tp.sigmets), 1)

    def test_150917_cancel(self):
        """Don't error out on a CANCELs SIGMET"""
        utcnow = utc(2015, 9, 17, 0, 0)
        tp = parser(get_file('SIGPAP_cancel.txt'), utcnow)
        self.assertEquals(len(tp.sigmets), 0)

    def test_compute_esol(self):
        """ Test our algo on either side of a line """
        pts = [[0, 0], [5, 0]]
        pts = compute_esol(pts, 111)
        print pts
        self.assertAlmostEqual(pts[0][0], 0.00, 2)
        self.assertAlmostEqual(pts[0][1], 1.00, 2)
        self.assertAlmostEqual(pts[1][0], 5.00, 2)
        self.assertAlmostEqual(pts[1][1], 1.00, 2)
        self.assertAlmostEqual(pts[2][0], 5.00, 2)
        self.assertAlmostEqual(pts[2][1], -1.00, 2)
        self.assertAlmostEqual(pts[3][0], 0.00, 2)
        self.assertAlmostEqual(pts[3][1], -1.00, 2)
        self.assertAlmostEqual(pts[4][0], 0.00, 2)
        self.assertAlmostEqual(pts[4][1], 1.00, 2)

    def test_150915_line(self):
        """ See about parsing a SIGMET LINE """
        utcnow = utc(2015, 9, 15, 2, 55)
        ugc_provider = {}
        nwsli_provider = {
            "MSP": dict(lon=-83.39, lat=44.45),
            "MCW": dict(lon=-85.50, lat=42.79),
        }
        tp = parser(get_file('SIGC_line.txt'), utcnow, ugc_provider,
                    nwsli_provider)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 0.47, 2)

    def test_150915_isol(self):
        """ See about parsing a SIGMET ISOL """
        utcnow = utc(2015, 9, 12, 23, 55)
        ugc_provider = {}
        nwsli_provider = {
            "FTI": dict(lon=-83.39, lat=44.45),
            "CME": dict(lon=-85.50, lat=42.79),
        }
        tp = parser(get_file('SIGC_ISOL.txt'), utcnow, ugc_provider,
                    nwsli_provider)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 0.30, 2)
        self.assertAlmostEquals(tp.sigmets[1].geom.area, 0.30, 2)

    def test_150915_nospace(self):
        """ See about parsing a SIGMET that has no spaces """
        utcnow = utc(2015, 9, 15, 15, 41)
        tp = parser(get_file('SIGAX.txt'), utcnow)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 23.47, 2)

    def test_140907_circle(self):
        """ See about parsing a SIGMET that is circle? """
        utcnow = utc(2014, 9, 6, 22, 15)
        tp = parser(get_file('SIGP0H.txt'), utcnow)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 11.70, 2)

    def test_140813_line(self):
        """ See about parsing a SIGMET that is a either side of line """
        utcnow = utc(2014, 8, 12, 13, 15)
        tp = parser(get_file('SIGP0A_line.txt'), utcnow)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 4.32, 2)

    def test_140815_cancel(self):
        """ See about parsing a SIGMET that is a either side of line """
        utcnow = utc(2014, 8, 15, 23, 41)
        tp = parser(get_file('SIG_cancel.txt'), utcnow)
        self.assertAlmostEquals(len(tp.sigmets), 0)

    def test_sigaoa(self):
        """ SIGAOA """
        utcnow = utc(2014, 8, 11, 19, 15)
        tp = parser(get_file('SIGA0A.txt'), utcnow)
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 24.35, 2)

    def test_sigaob(self):
        """ See about parsing 50E properly """
        utcnow = utc(2014, 8, 11, 19, 15)
        tp = parser(get_file('SIGA0B.txt'), utcnow)
        self.assertEquals(len(tp.sigmets), 0)

    def test_50e(self):
        """ See about parsing 50E properly """
        utcnow = utc(2014, 8, 11, 18, 55)
        ugc_provider = {}
        nwsli_provider = {
            "ASP": dict(lon=-83.39, lat=44.45),
            "ECK": dict(lon=-82.72, lat=43.26),
            "GRR": dict(lon=-85.50, lat=42.79),
        }

        tp = parser(get_file('SIGE3.txt'), utcnow, ugc_provider,
                    nwsli_provider)
        # tp.draw()
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 2.15, 2)

    def test_sigc(self):
        """ See about parsing SIGC """
        utcnow = utc(2014, 8, 11, 16, 55)
        ugc_provider = {}
        nwsli_provider = {}
        for sid in ("MSL,SJI,MLU,LIT,BTR,LEV,LCH,IAH,YQT,SAW,SAT,DYC,AXC,"
                    "ODI,DEN,TBE,ADM,JCT,INK,ELP").split(","):
            nwsli_provider[sid] = dict(lon=-99, lat=45)

        tp = parser(get_file('SIGC.txt'), utcnow, ugc_provider, nwsli_provider)
        # tp.draw()
        j = tp.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(tp.sigmets[0].ets, utc(2014, 8, 11, 18, 55))
        self.assertEquals(j[0][0], ('KKCI issues SIGMET 62C for AL MS LA AR '
                                    'till 1855 UTC'))
        self.assertEquals(j[1][0], ('KKCI issues SIGMET 63C for LA TX AND MS '
                                    'LA TX CSTL WTRS till 1855 UTC'))

    def test_sigpat(self):
        """ Make sure we don't have another failure with geom parsing """
        utcnow = utc(2014, 8, 11, 12, 34)
        tp = parser(get_file('SIGPAT.txt'), utcnow)
        j = tp.get_jabbers('http://localhost', 'http://localhost')
        self.assertAlmostEquals(tp.sigmets[0].geom.area, 33.71, 2)
        self.assertEquals(tp.sigmets[0].sts, utc(2014, 8, 11, 12, 35))
        self.assertEquals(tp.sigmets[0].ets, utc(2014, 8, 11, 16, 35))
        self.assertEquals(j[0][0], 'PHFO issues SIGMET TANGO 1 till 1635 UTC')
