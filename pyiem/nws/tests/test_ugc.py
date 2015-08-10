import unittest
import datetime
import pytz
from pyiem.nws import ugc

STR1 = "DCZ001-170200-"
STR2 = "DCZ001-MDZ004>007-009>011-013-014-016>018-VAZ036>042-050>057-170200-"


class TestObservation(unittest.TestCase):

    def test_totextstr(self):
        """ See if we can generate a proper string from a UGCS """
        ugcs = [ugc.UGC("DC", "Z", "001"), ugc.UGC("IA", "C", "001"),
                ugc.UGC("IA", "C", "002")]
        self.assertEquals(ugc.ugcs_to_text(ugcs),
                          "((IAC001)), ((IAC002)) [IA] and ((DCZ001)) [DC]")

    def test_str1(self):
        """ check ugc.parse of STR1 parsing """
        valid = datetime.datetime(2008, 12, 17, 3, 0)
        valid = valid.replace(tzinfo=pytz.timezone('UTC'))
        (ugcs, expire) = ugc.parse(STR1, valid)

        expire_answer = valid.replace(hour=2)
        ugcs_answer = [ugc.UGC("DC", "Z", "001"), ]

        self.assertEqual(ugcs, ugcs_answer)
        self.assertEqual(expire, expire_answer)

    def test_str2(self):
        """ check ugc.parse of STR2 parsing """
        valid = datetime.datetime(2008, 12, 17, 3, 0)
        valid = valid.replace(tzinfo=pytz.timezone('UTC'))
        (ugcs, expire) = ugc.parse(STR2, valid)

        expire_answer = valid.replace(hour=2)
        ugcs_answer = [ugc.UGC("DC", "Z", "001"), ugc.UGC("MD", "Z", "004"),
                       ugc.UGC("MD", "Z", "005"), ugc.UGC("MD", "Z", "006"),
                       ugc.UGC("MD", "Z", "007"), ugc.UGC("MD", "Z", "009"),
                       ugc.UGC("MD", "Z", "010"), ugc.UGC("MD", "Z", "011"),
                       ugc.UGC("MD", "Z", "013"), ugc.UGC("MD", "Z", "014"),
                       ugc.UGC("MD", "Z", "016"), ugc.UGC("MD", "Z", "017"),
                       ugc.UGC("MD", "Z", "018"), ugc.UGC("VA", "Z", "036"),
                       ugc.UGC("VA", "Z", "037"), ugc.UGC("VA", "Z", "038"),
                       ugc.UGC("VA", "Z", "039"), ugc.UGC("VA", "Z", "040"),
                       ugc.UGC("VA", "Z", "041"), ugc.UGC("VA", "Z", "042"),
                       ugc.UGC("VA", "Z", "050"), ugc.UGC("VA", "Z", "051"),
                       ugc.UGC("VA", "Z", "052"), ugc.UGC("VA", "Z", "053"),
                       ugc.UGC("VA", "Z", "054"), ugc.UGC("VA", "Z", "055"),
                       ugc.UGC("VA", "Z", "056"), ugc.UGC("VA", "Z", "057")]

        self.assertEqual(ugcs, ugcs_answer)
        self.assertEqual(expire, expire_answer)
