"""Test HVTEC."""
from pyiem.nws import hvtec


def test_badtime():
    """Make sure contime errors"""
    v = hvtec.contime("BAD")
    assert v is None


def test_empty():
    """check empty HVTEC Parsing"""
    v = hvtec.parse("/00000.0.ER.000000T0000Z.000000T0000Z.000000T0000Z.OO/")
    assert v[0].nwsli.id == "00000"


def test_empty2():
    """Test empty."""
    initial = "/NWYI3.0.ER.000000T0000Z.000000T0000Z.000000T0000Z.OO/"
    v = hvtec.parse(initial)
    assert v[0].nwsli.id == "NWYI3"
    assert str(v[0]) == initial
