import unittest
from pyiem import datatypes


class TestDatatypes(unittest.TestCase):

    def test_unitserror(self):
        """ Make sure that unknown units actually raise an error """
        for _, cls in datatypes.__dict__.items():
            if isinstance(cls, type) and hasattr(cls, 'known_units'):
                a = cls(10, cls.known_units[0])
                self.assertRaises(datatypes.UnitsError, a.value, 'ZZzZZ')
                for unit in cls.known_units:
                    a = cls(10, unit)
                    for unit in cls.known_units:
                        self.assertTrue(a.value(unit) is not None)

    def test_mixingratio(self):
        """ Mixing Ratio"""
        mixr = datatypes.mixingratio(10, 'KG/KG')
        self.assertEquals(mixr.value('KG/KG'), 10)

    def test_temp_bad_units(self):
        """ Simple check of bad units in temperature """
        self.assertRaises(datatypes.UnitsError, datatypes.temperature,
                          -99, 'Q')

    def test_temp_same_units(self):
        """ Temperature data in equals data out """
        value = 100.0
        tmpf = datatypes.temperature(value, 'F')
        self.assertEquals(value, tmpf.value('F'))

    def test_temp_conv(self):
        """ Temperature convert from Celsius to Fahrenheit to Kelvin"""
        c = datatypes.temperature(100.0, 'C')
        self.assertEquals(212, c.value('F'))
        self.assertEquals(100.0, c.value('C'))
        self.assertEquals(373.15, c.value('K'))

    def test_press_conv(self):
        """ Pressure convert from MB to IN to HPA"""
        hpa = datatypes.pressure(850.0, 'HPA')
        self.assertEquals(850.0, hpa.value('MB'))
        self.assertAlmostEquals(25.10, hpa.value('in'), 2)
        hpa = datatypes.pressure(85000.0, 'PA')
        self.assertAlmostEquals(25.10, hpa.value('IN'), 2)

    def test_speed_conv(self):
        """ Speed convert from KT to MPS to KMH to MPH """
        mph = datatypes.speed(58.0, 'MPH')
        self.assertAlmostEquals(50.4, mph.value('KT'), 1)
        self.assertAlmostEquals(25.93, mph.value('mps'), 2)
        self.assertAlmostEquals(93.33, mph.value('KMH'), 2)

    def test_precipitation_conv(self):
        """ Speed precipitation from MM to CM to IN """
        cm = datatypes.precipitation(25.4, 'CM')
        self.assertAlmostEquals(10.0, cm.value('IN'), 1)
        self.assertAlmostEquals(254.0, cm.value('MM'), 1)

    def test_distance_conv(self):
        """ Speed distance from M to MI to FT to SM to KM """
        mi = datatypes.distance(1.0, 'mi')
        self.assertAlmostEquals(1609.344, mi.value('M'), 1)
        self.assertAlmostEquals(5280.0, mi.value('FT'), 1)
        self.assertAlmostEquals(1.0, mi.value('SM'), 1)
        self.assertAlmostEquals(1.61, mi.value('KM'), 2)
        self.assertAlmostEquals(63360.00, mi.value('IN'), 2)
        self.assertAlmostEquals(1609344.00, mi.value('mm'), 2)
        self.assertAlmostEquals(160934.40, mi.value('CM'), 2)

    def test_direction_conv(self):
        """ Direction, which is DEG to RAD """
        mi = datatypes.direction(360, 'DEG')
        self.assertAlmostEquals(6.2831853, mi.value('rad'), 4)
        mi = datatypes.direction(3.14159, 'RAD')
        self.assertAlmostEquals(180.0, mi.value('DEG'), 1)
