"""tests"""
from pyiem import nwnformat


def test_heatindex():
    """Exercise the heatindex func"""
    d = nwnformat.heatidx(100, 50)
    assert abs(d - 119.48) < 0.01
    d = nwnformat.heatidx(69, 50)
    assert abs(d - 69.00) < 0.01
    d = nwnformat.heatidx(169, 50)
    assert abs(d - -99.00) < 0.01
    d = nwnformat.heatidx(79, 0)
    assert abs(d - -99.00) < 0.01
    d = nwnformat.heatidx(75, 40)
    assert abs(d - 73.16) < 0.01
    d = nwnformat.wchtidx(15, 1)
    assert abs(d - 15.00) < 0.01


def test_feels():
    """test the output of the feelslike() method"""
    d = nwnformat.feelslike(100, 50, 10)
    assert abs(d - 119.485) < 0.001
    d = nwnformat.feelslike(10, 50, 10)
    assert abs(d - -3.54) < 0.01


def test_mydir():
    """test the output of the mydir() method"""
    d = nwnformat.mydir(10, 10)
    assert d == 225
    d = nwnformat.mydir(-10, 10)
    assert d == 135
    d = nwnformat.mydir(-10, -10)
    assert d == 45
    d = nwnformat.mydir(10, -10)
    assert d == 315
    d = nwnformat.mydir(10, 0)
    assert d == 270


def test_dwpf():
    """test the output of the dwpf() method"""
    d = nwnformat.dwpf(50, 50)
    assert d == 32
    assert nwnformat.dwpf(None, 32) is None


def test_uv():
    """test the output of the uv() method"""
    u, v = nwnformat.uv(10, 180)
    assert u == 0
    assert v == 10


def test_basic():
    """basic test of constructor"""
    n = nwnformat.nwnformat()
    n.sid = 100
    n.parseLineRT(
        (
            "A 263  14:58 07/16/15   S 09MPH 000K 460F 460F "
            '100% 29.66F 00.00"D 00.00"M 00.00"R'
        ).split()
    )
    n.parseLineRT(
        (
            "A 263    Max 07/16/15   S 21MPH 000K 460F 460F "
            '100% 29.81" 00.00"D 00.00"M 00.00"R'
        ).split()
    )
    n.parseLineRT(
        (
            "A 263    Min 07/16/15   S 01MPH 000K 460F 882F "
            '100% 29.65" 00.00"D 00.00"M 00.00"R'
        ).split()
    )
    n.parseLineRT(
        (
            "A 263  14:59 07/16/15   S 19MPH 000K 460F 460F "
            '100% 29.66F 00.00"D 00.00"M 00.00"R'
        ).split()
    )
    # n.setTS("BAH")
    # self.assertEqual(n.error, 100)
    n.setTS("07/16/15 14:58:50")
    n.sanityCheck()
    n.avgWinds()
    n.currentLine()
    n.maxLine()
    n.minLine()
    assert abs(n.pres - 29.66) < 0.01
