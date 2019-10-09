"""tests"""
import datetime

from pyiem import prism


def test_ij():
    """Can we get valid indices back!"""
    res = prism.find_ij(-98.0, 32)
    assert res[0] == 647

    res = prism.find_ij(98.0, 32)
    assert res[0] is None


def test_tidx():
    """Can we get time indices"""
    valid = datetime.datetime(2017, 9, 1)
    tidx = prism.daily_offset(valid)
    assert tidx == 243
