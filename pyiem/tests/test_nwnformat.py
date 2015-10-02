import unittest
from pyiem import nwnformat


class TestNWNFORMAT(unittest.TestCase):

    def test_heatindex(self):
        """Exercise the heatindex func"""
        d = nwnformat.heatidx(100, 50)
        self.assertAlmostEqual(d, 119.48, 2)
        d = nwnformat.heatidx(69, 50)
        self.assertAlmostEqual(d, 69.00, 2)
        d = nwnformat.heatidx(169, 50)
        self.assertAlmostEqual(d, -99.00, 2)
        d = nwnformat.heatidx(79, 0)
        self.assertAlmostEqual(d, -99.00, 2)
        d = nwnformat.heatidx(75, 40)
        self.assertAlmostEqual(d, 73.16, 2)
        d = nwnformat.wchtidx(15, 1)
        self.assertAlmostEqual(d, 15.00, 2)

    def test_feels(self):
        """test the output of the feelslike() method"""
        d = nwnformat.feelslike(100, 50, 10)
        self.assertAlmostEquals(d, 119.485, 3)
        d = nwnformat.feelslike(10, 50, 10)
        self.assertAlmostEquals(d, -3.54, 2)

    def test_mydir(self):
        """test the output of the mydir() method"""
        d = nwnformat.mydir(10, 10)
        self.assertAlmostEquals(d, 225)
        d = nwnformat.mydir(-10, 10)
        self.assertAlmostEquals(d, 135)
        d = nwnformat.mydir(-10, -10)
        self.assertAlmostEquals(d, 45)
        d = nwnformat.mydir(10, -10)
        self.assertAlmostEquals(d, 315)
        d = nwnformat.mydir(10, 0)
        self.assertAlmostEquals(d, 270)

    def test_dwpf(self):
        """test the output of the dwpf() method"""
        d = nwnformat.dwpf(50, 50)
        self.assertAlmostEqual(d, 32)
        self.assertTrue(nwnformat.dwpf(None, 32) is None)

    def test_uv(self):
        """test the output of the uv() method"""
        u, v = nwnformat.uv(10, 180)
        self.assertAlmostEqual(u, 0)
        self.assertAlmostEqual(v, 10)

    def test_basic(self):
        ''' basic test of constructor '''
        n = nwnformat.nwnformat()
        n.sid = 100
        n.parseLineRT(('A 263  14:58 07/16/15   S 09MPH 000K 460F 460F '
                       '100% 29.66F 00.00"D 00.00"M 00.00"R').split())
        n.parseMaxLineRT(('A 263    Max 07/16/15   S 21MPH 000K 460F 460F '
                          '100% 29.81" 00.00"D 00.00"M 00.00"R').split())
        n.parseMaxLineRT(('A 263    Min 07/16/15   S 01MPH 000K 460F 882F '
                          '100% 29.65" 00.00"D 00.00"M 00.00"R').split())
        n.parseLineRT(('A 263  14:59 07/16/15   S 19MPH 000K 460F 460F '
                       '100% 29.66F 00.00"D 00.00"M 00.00"R').split())
        # n.setTS("BAH")
        # self.assertEqual(n.error, 100)
        n.setTS("07/16/15 14:58:50")
        n.sanityCheck()
        n.avgWinds()
        n.currentLine()
        n.maxLine()
        n.minLine()
        self.assertAlmostEqual(n.pres, 29.66, 2)
