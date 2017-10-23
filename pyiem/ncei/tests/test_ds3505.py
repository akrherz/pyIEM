"""Tests for the DS3505 format"""
import unittest

from pyiem.ncei.ds3505 import parser


class DS3505(unittest.TestCase):
    """Go for it"""

    def test_metar(self):
        """Can we replicate an actual METAR"""
        # IEM METAR database has this for 1 Jan 2016
        # KAMW 010713Z AUTO 29013KT 10SM BKN017 OVC033 M05/M08 A3028 RMK
        #    AO2 T10501083
        msg = ("0232725472949892016010107137+41991-093619FM-16+0291KAMW "
               "V0302905N00675005185MN0160935N5-00505-00835999999ADDGA1075+"
               "005185999GA2085+010065999GD13991+0051859GD24991+0100659"
               "GE19MSL   +99999+99999GF199999999999005181999999MA1102545"
               "099065REMMET09501/01/16 01:13:02 SPECI KAMW 010713Z "
               "29013KT 10SM BKN017 OVC033 M05/M08 A3028 RMK AO2 T10501083")
        data = parser(msg, add_metar=True)
        self.assertEqual(data['metar'],
                         ("KAMW 010713Z AUTO 29013KT 10SM BKN017 OVC033 "
                          "M05/M08 A3028 RMK T10501083"))

    def test_basic(self):
        """Can we parse it, yes we can"""
        msg = ("0114010010999991988010100004+70933-008667FM-12+0009ENJA "
               "V0203301N01851220001CN0030001N9-02011-02211100211ADDAA10"
               "6000091AG14000AY131061AY221061GF102991021051008001001001"
               "MD1710141+9999MW1381OA149902631REMSYN011333   91151")
        data = parser(msg, add_metar=True)
        self.assertTrue(data is not None)
        self.assertEqual(data['metar'], 'ENJA 010000Z AUTO 33035KT')

    def test_read(self):
        """Can we process an entire file?"""
        for line in open("../../../data/product_examples/NCEI/DS3505.txt"):
            data = parser(line.strip())
            self.assertTrue(data is not None)

        for line in open(("../../../data/product_examples/NCEI/"
                          "DS3505_KAMW_2016.txt")):
            data = parser(line.strip())
            self.assertTrue(data is not None)
