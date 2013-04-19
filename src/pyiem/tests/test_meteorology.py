import unittest
from pyiem import datatypes, meteorology

class TestDatatypes(unittest.TestCase):

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