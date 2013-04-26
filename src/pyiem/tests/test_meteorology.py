import unittest
import numpy as np
from pyiem import datatypes, meteorology

class TestDatatypes(unittest.TestCase):

    def test_uv(self):
        """ Test calculation of uv wind components """
        u,v = meteorology.uv(10, 0)
        self.assertEqual(u, 0.)
        self.assertEqual(v, -10.)

        u,v = meteorology.uv(np.array([10,20,15]), np.array([90,180,135]))
        self.assertEqual(u[0], -10)
        self.assertEqual(v[1], 20.)
        self.assertAlmostEquals(v[2], 10.6, 1)


    def test_relh(self):
        """ Simple check of bad units in temperature """
        tmp = datatypes.temperature(24, 'C')
        dwp = datatypes.temperature(24, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertEquals(100.0, relh)
        
        tmp = datatypes.temperature(32, 'C')
        dwp = datatypes.temperature(10, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(25.79, relh, 2)