import unittest
from pyiem import nwnformat


class TestNWNFORMAT(unittest.TestCase):

    def test_basic(self):
        ''' basic test of constructor '''
        n = nwnformat.nwnformat()
        n.parseLineRT(('A 263  14:58 07/16/15   S 09MPH 000K 460F 460F '
                       '100% 29.66F 00.00"D 00.00"M 00.00"R').split())
        n.parseMaxLineRT(('A 263    Max 07/16/15   S 21MPH 000K 460F 460F '
                          '100% 29.81" 00.00"D 00.00"M 00.00"R').split())
        n.parseMaxLineRT(('A 263    Min 07/16/15   S 01MPH 000K 460F 882F '
                          '100% 29.65" 00.00"D 00.00"M 00.00"R').split())
        self.assertEqual(n.pres, '29.66')
