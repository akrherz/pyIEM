"""test lsr."""

from pyiem.nws.products.lsr import _mylowercase
from pyiem.nws.products import lsr


def test_mag_string():
    """ Magnitude string for various events """
    lr = lsr.LSR()
    lr.typetext = "TSTM WND GST"
    lr.magnitude_units = "MPH"
    lr.magnitude_f = 59
    lr.magnitude_qualifier = 'M'
    assert lr.mag_string() == "TSTM WND GST of M59 MPH"


def test_get_dbtype():
    ''' See what we get for a given LSR typetext '''
    lr = lsr.LSR()
    lr.typetext = "TORNADO"
    assert lr.get_dbtype() == 'T'


def test_lowercase():
    ''' Make sure we can properly convert cities to mixed case '''
    assert _mylowercase("1 N AMES") == "1 N Ames"
    assert _mylowercase("1 NNW AMES") == "1 NNW Ames"
