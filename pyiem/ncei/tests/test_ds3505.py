"""Tests for the DS3505 format"""
import unittest

from pyiem.ncei.ds3505 import parser

class DS3505(unittest.TestCase):
    """Go for it"""

    def test_basic(self):
        """Can we parse it, yes we can"""
        msg = ("0114010010999991988010100004+70933-008667FM-12+0009ENJA "
               "V0203301N01851220001CN0030001N9-02011-02211100211ADDAA10"
               "6000091AG14000AY131061AY221061GF102991021051008001001001"
               "MD1710141+9999MW1381OA149902631REMSYN011333   91151")
        data = parser(msg)
        self.assertTrue(data is not None)

    def test_read(self):
        """Can we process an entire file?"""
        for line in open("../../../data/product_examples/NCEI/DS3505.txt"):
            data = parser(line.strip())
            self.assertTrue(data is not None)
