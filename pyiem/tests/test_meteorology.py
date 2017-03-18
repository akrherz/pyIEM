import unittest
import numpy as np
from pyiem import datatypes, meteorology


class TestCase(unittest.TestCase):

    def test_vectorized(self):
        """See that heatindex and windchill can do lists"""
        temp = datatypes.temperature([0, 10], 'F')
        sknt = datatypes.speed([30, 40], 'MPH')
        val = meteorology.windchill(temp, sknt).value('F')
        self.assertAlmostEquals(val[0], -24.50, 2)

        t = datatypes.temperature([80.0, 90.0], 'F')
        td = datatypes.temperature([70.0, 60.0], 'F')
        hdx = meteorology.heatindex(t, td)
        self.assertAlmostEqual(hdx.value("F")[0], 83.93, 2)

    def test_gdd_with_nans(self):
        """Can we properly deal with nan's and not emit warnings?"""
        highs = np.ma.array([70, 80, np.nan, 90],
                            mask=[False, False, True, False])
        lows = highs - 10
        r = meteorology.gdd(datatypes.temperature(highs, 'F'),
                            datatypes.temperature(lows, 'F'),
                            50, 86)
        self.assertTrue(np.ma.is_masked(r[2]))

    def test_gdd(self):
        """Growing Degree Days"""
        r = meteorology.gdd(datatypes.temperature(86, 'F'),
                            datatypes.temperature(50, 'F'),
                            50, 86)
        self.assertEquals(r, 18)

        r = meteorology.gdd(datatypes.temperature(51, 'F'),
                            datatypes.temperature(49, 'F'),
                            50, 86)
        self.assertAlmostEquals(r, 0.5, 1)

        r = meteorology.gdd(datatypes.temperature(49, 'F'),
                            datatypes.temperature(40, 'F'),
                            50, 86)
        self.assertEquals(r, 0)

        r = meteorology.gdd(datatypes.temperature([86, 86], 'F'),
                            datatypes.temperature([50, 50], 'F'),
                            50, 86)
        self.assertEquals(r[0], 18)
        self.assertEquals(r[1], 18)

    def test_mixingratio(self):
        """Test the mixing ratio calculation"""
        r = meteorology.mixing_ratio(datatypes.temperature(70, 'F'))
        self.assertAlmostEquals(r.value('KG/KG'), 0.016, 3)

    def test_sw(self):
        """Test shortwave flux calculation"""
        r = meteorology.clearsky_shortwave_irradiance_year(42, 100)
        self.assertAlmostEquals(r[0], 7.20, 2)
        self.assertAlmostEquals(r[90], 22.45, 2)
        self.assertAlmostEquals(r[182], 32.74, 2)
        self.assertAlmostEquals(r[270], 19.07, 2)
        self.assertAlmostEquals(r[364], 7.16, 2)

    def test_drct(self):
        """Conversion of u and v to direction"""
        self.assertEquals(
            meteorology.drct(datatypes.speed(np.array([10, 20]), 'KT'),
                             datatypes.speed(np.array([10, 20]), 'KT')
                             ).value("DEG")[0], 225)
        self.assertEquals(meteorology.drct(datatypes.speed(-10, 'KT'),
                                           datatypes.speed(10, 'KT')
                                           ).value("DEG"), 135)
        self.assertEquals(meteorology.drct(datatypes.speed(-10, 'KT'),
                                           datatypes.speed(-10, 'KT')
                                           ).value("DEG"), 45)
        self.assertEquals(meteorology.drct(datatypes.speed(10, 'KT'),
                                           datatypes.speed(-10, 'KT')
                                           ).value("DEG"), 315)

    def test_windchill(self):
        """Wind Chill Conversion"""
        temp = datatypes.temperature(0, 'F')
        sknt = datatypes.speed(30, 'MPH')
        val = meteorology.windchill(temp, sknt).value('F')
        self.assertAlmostEquals(val, -24.50, 2)

    def test_dewpoint_from_pq(self):
        """ See if we can produce dew point from pressure and mixing ratio """
        p = datatypes.pressure(1013.25, "MB")
        mr = datatypes.mixingratio(0.012, "kg/kg")
        dwpk = meteorology.dewpoint_from_pq(p, mr)
        self.assertAlmostEqual(dwpk.value("C"), 16.84, 2)

    def test_dewpoint(self):
        """ test out computation of dew point """
        for t0, r0, a0 in [[80, 80, 73.42], [80, 20, 35.87]]:
            t = datatypes.temperature(t0, 'F')
            rh = datatypes.humidity(r0, '%')
            dwpk = meteorology.dewpoint(t, rh)
            self.assertAlmostEqual(dwpk.value("F"), a0, 2)

    def test_heatindex(self):
        ''' Test our heat index calculations '''
        t = datatypes.temperature(80.0, 'F')
        td = datatypes.temperature(70.0, 'F')
        hdx = meteorology.heatindex(t, td)
        self.assertAlmostEqual(hdx.value("F"), 83.93, 2)

        t = datatypes.temperature(30.0, 'F')
        hdx = meteorology.heatindex(t, td)
        self.assertAlmostEqual(hdx.value("F"), 30.00, 2)

    def test_uv(self):
        """ Test calculation of uv wind components """
        speed = datatypes.speed([10, ], 'KT')
        mydir = datatypes.direction([0, ], 'DEG')
        u, v = meteorology.uv(speed, mydir)
        self.assertEqual(u.value("KT"), 0.)
        self.assertEqual(v.value("KT"), -10.)

        speed = datatypes.speed([10, 20, 15], 'KT')
        mydir = datatypes.direction([90, 180, 135], 'DEG')
        u, v = meteorology.uv(speed, mydir)
        self.assertEqual(u.value("KT")[0], -10)
        self.assertEqual(v.value("KT")[1], 20.)
        self.assertAlmostEquals(v.value("KT")[2], 10.6, 1)

    def test_relh(self):
        """ Simple check of bad units in temperature """
        tmp = datatypes.temperature(24, 'C')
        dwp = datatypes.temperature(24, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertEquals(100.0, relh.value("%"))

        tmp = datatypes.temperature(32, 'C')
        dwp = datatypes.temperature(10, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(25.79, relh.value("%"), 2)

        tmp = datatypes.temperature(32, 'C')
        dwp = datatypes.temperature(15, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(35.81, relh.value("%"), 2)

        tmp = datatypes.temperature(5, 'C')
        dwp = datatypes.temperature(4, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(93.24, relh.value("%"), 2)
