"""tests"""

import datetime

from pyiem import prism


def test_edges():
    """Test that we get the right answer for the edges."""
    res = prism.find_ij(prism.WEST_EDGE, prism.NORTH_EDGE - 0.01)
    assert res[0] == 0
    assert res[1] == prism.NY - 1

    res = prism.find_ij(prism.EAST_EDGE - 0.01, prism.SOUTH_EDGE)
    assert res[0] == prism.NX - 1
    assert res[1] == 0


def test_ij():
    """Can we get valid indices back!"""
    res = prism.find_ij(-98.0, 32)
    assert res[0] == 648

    res = prism.find_ij(98.0, 32)
    assert res[0] is None


def test_tidx():
    """Can we get time indices"""
    valid = datetime.datetime(2017, 9, 1)
    tidx = prism.daily_offset(valid)
    assert tidx == 243
