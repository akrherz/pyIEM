import unittest
from pyiem import nwnformat


class TestNWNFORMAT(unittest.TestCase):

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

    def test_dwpf(self):
        """test the output of the dwpf() method"""
        d = nwnformat.dwpf(50, 50)
        self.assertAlmostEqual(d, 32)

    def test_uv(self):
        """test the output of the uv() method"""
        u, v = nwnformat.uv(10, 180)
        self.assertAlmostEqual(u, 0)
        self.assertAlmostEqual(v, 10)

    def test_basic(self):
        ''' basic test of constructor '''
        n = nwnformat.nwnformat()
        n.parseLineRT(('A 263  14:58 07/16/15   S 09MPH 000K 460F 460F '
                       '100% 29.66F 00.00"D 00.00"M 00.00"R').split())
        n.parseMaxLineRT(('A 263    Max 07/16/15   S 21MPH 000K 460F 460F '
                          '100% 29.81" 00.00"D 00.00"M 00.00"R').split())
        n.parseMaxLineRT(('A 263    Min 07/16/15   S 01MPH 000K 460F 882F '
                          '100% 29.65" 00.00"D 00.00"M 00.00"R').split())
        n.parseLineRT(('A 263  14:59 07/16/15   S 19MPH 000K 460F 460F '
                       '100% 29.66F 00.00"D 00.00"M 00.00"R').split())
        n.avgWinds()
        n.currentLine()
        n.maxLine()
        n.minLine()
        self.assertEqual(n.pres, '29.66')
