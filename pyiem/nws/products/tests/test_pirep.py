import os
import datetime
import pytz
import unittest
from pyiem.nws.products.pirep import parser as pirepparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour, minute).replace(
                        tzinfo=pytz.timezone("UTC"))

class TestProducts(unittest.TestCase):
    """ Tests """
    def test_150202_groupdict(self):
        """groupdict.txt threw an error"""
        nwsli_provider = {'GCC': {'lat': 44.26, 'lon': -88.52}}
        prod = pirepparser(get_file("PIREPS/groupdict.txt"),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.reports), 1)

    def test_150202_airmet(self):
        """airmet.txt has no valid data, so don't error out """
        prod = pirepparser(get_file('PIREPS/airmet.txt'))
        self.assertEquals(len(prod.reports), 0)

    def test_150126_space(self):
        """ space.txt has a space where it should not """
        nwsli_provider = {'CZBA': {'lat': 44.26, 'lon': -88.52}}
        prod = pirepparser(get_file('PIREPS/space.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertAlmostEquals(prod.reports[0].latitude, 44.15, 2)
        
    def test_150121_offset(self):
        """ offset.txt and yet another /OV iteration """
        nwsli_provider = {'MRF': {'lat': 44.26, 'lon': -88.52},
                          'PDT': {'lat': 44.26, 'lon': -88.52},
                          'HQZ': {'lat': 44.26, 'lon': -88.52}}
        prod = pirepparser(get_file('PIREPS/offset.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertAlmostEquals(prod.reports[0].latitude, 44.48, 2)
        self.assertAlmostEquals(prod.reports[1].latitude, 44.26, 2)
        self.assertAlmostEquals(prod.reports[2].latitude, 44.22, 2)

    def test_150121_runway(self):
        """ runway.txt has KATW on the runway, this was not good """
        nwsli_provider = {'ATW': {'lat': 44.26, 'lon': -88.52},
                          'IPT': {'lat': 44.26, 'lon': -88.52}}
        prod = pirepparser(get_file('PIREPS/runway.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertAlmostEquals(prod.reports[0].latitude, 44.26, 2)
        self.assertAlmostEquals(prod.reports[1].longitude, -88.52, 2)
        
    def test_150121_fourchar(self):
        """ Another coding edition with four char identifiers """
        nwsli_provider = {'FAR': {'lat': 44, 'lon': -99},
                          'SMF': {'lat': 42, 'lon': -99},
                          'RDD': {'lat': 43, 'lon': -100}}
        prod = pirepparser(get_file('PIREPS/fourchar.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertAlmostEquals(prod.reports[0].latitude, 44.10, 2)
        self.assertAlmostEquals(prod.reports[1].latitude, 42.50, 2)
    
    def test_150120_latlonloc(self):
        """ latlonloc.txt Turns out there is a LAT/LON option for OV """
        prod = pirepparser(get_file('PIREPS/latlonloc.txt'))
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertEquals(prod.reports[0].latitude, 25.00)
        self.assertEquals(prod.reports[0].longitude, -70.00)
        self.assertEquals(prod.reports[1].latitude, 39.00)
        self.assertEquals(prod.reports[1].longitude, -45.00)

        prod = pirepparser(get_file('PIREPS/latlonloc2.txt'))
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

        nwsli_provider = {'PKTN': {'lat': 44, 'lon': -99}}
        prod = pirepparser(get_file('PIREPS/PKTN.txt'), nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    
    def test_150120_OVO(self):
        """ PIREPS/OVO.txt has a location of OV 0 """
        nwsli_provider = {'AVK': {'lat': 44, 'lon': 99}}
        prod = pirepparser(get_file('PIREPS/OVO.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    def test_offset(self):
        """ Test out our displacement logic """
        lat = 42.5
        lon = -92.5
        nwsli_provider = {'BIL': {'lat': lat, 'lon': lon}}
        p = pirepparser("\001\r\r\n000 \r\r\nUBUS01 KMSC 090000\r\r\n", 
                        nwsli_provider=nwsli_provider)
        lon2, lat2 = p.compute_loc("BIL", 0, 0)
        self.assertEquals(lon2, lon)
        self.assertEquals(lat2, lat)

        lon2, lat2 = p.compute_loc("BIL", 100, 90)
        self.assertAlmostEquals(lon2, -90.54, 2)
        self.assertEquals(lat2, lat)

        lon2, lat2 = p.compute_loc("BIL", 100, 0)
        self.assertEquals(lon2, lon)
        self.assertAlmostEquals(lat2, 43.95, 2)


    def test_1(self):
        """ PIREP.txt, can we parse it! """
        utcnow = utc(2015,1,9,0,0)
        nwsli_provider = {'BIL': {'lat': 44, 'lon': 99},
                          'LBY': {'lat': 45, 'lon': 100},
                          'PUB': {'lat': 46, 'lon': 101},
                          'HPW': {'lat': 47, 'lon': 102}}
        prod = pirepparser(get_file('PIREP.txt'), utcnow=utcnow,
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        
        j = prod.get_jabbers()
        self.assertEquals(j[0][2]['channels'], 'UA.None,UA.PIREP')
