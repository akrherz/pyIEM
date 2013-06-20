import unittest

from pyiem import datatypes, meteorology

class TestDatatypes(unittest.TestCase):

    def test_uv(self):
        """ Test calculation of uv wind components """
        speed = datatypes.speed([10,], 'KT')
        mydir = datatypes.direction([0,], 'DEG')
        u,v = meteorology.uv(speed, mydir)
        self.assertEqual(u.value("KT"), 0.)
        self.assertEqual(v.value("KT"), -10.)

        speed = datatypes.speed([10,20,15], 'KT')
        mydir = datatypes.direction([90,180,135], 'DEG')
        u,v = meteorology.uv(speed, mydir)
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