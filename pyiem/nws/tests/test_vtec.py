"""Unit tests for pyiem.nws.vtec"""

from pyiem.util import utc
from pyiem.nws import vtec


def test_fireweather():
    """Do we return different things for FW"""
    res = vtec.get_ps_string("FW", "A")
    assert res == "Fire Weather Watch"
    res = vtec.get_ps_string("FW", "W")
    assert res == "Red Flag Warning"


def test_get_id():
    """check that getID() works as we expect"""
    vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
    assert vc[0].get_id(2005) == '2005-KJAN-TO-W-0130'


def test_endstring():
    """Make sure that the end time string is empty for cancel action"""
    vc = vtec.parse("/O.CAN.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
    assert vc[0].get_end_string(None) == ''


def test_begints():
    """ check vtec.begints Parsing """
    vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
    ts = utc(2005, 8, 29, 16, 51)
    assert vc[0].begints == ts


def test_endts():
    """ check vtec.endts Parsing """
    vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
    ts = utc(2005, 8, 29, 18, 15)
    assert vc[0].endts == ts


def test_product_string():
    """ check vtec.product_string() formatting """
    vc = vtec.parse("/O.NEW.KJAN.TO.W.0130.050829T1651Z-050829T1815Z/")
    assert vc[0].product_string() == "issues Tornado Warning"
