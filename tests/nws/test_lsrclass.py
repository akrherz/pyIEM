"""test lsr."""

import pytest
from pyiem.nws.products.lsr import _mylowercase
from pyiem.nws.lsr import _icestorm_remark as ir
from pyiem.nws.products import lsr


@pytest.mark.parametrize(
    "text, ans",
    [
        ("AROUND ONE QUARTER OF AN INCH", 0.25),
        ("0.25 INCH ICE ACCUMULATION", 0.25),
        ("OF 1 INCH", 1.0),
        (".25 TO .3 INCHES", 0.3),
        ("0.5 INCHES", 0.5),
        ("A QUARTER TO HALF INCH OF ICE", 0.5),
        ("LIMBS 6 TO 10 INCHES IN DIAMETER. THREE-TENTHS OF AN INCH", 0.3),
        ("ONE QUARTER INCH OF ICE ACCUMULATION", 0.25),
        ("3/8THS OF AN INCH", 0.375),
        ("3 TENTHS OF AN INCH", 0.3),
        ("3/16 INCH ICE ACCRETION REPORTED.", 0.1875),
    ],
)
def test_icestorm_remark(text, ans):
    """Ripping out a magnitude from the remark text."""
    assert ir(text) == ans


def test_icestorm_remark_none():
    """Make sure a None or empty remark causes grief."""
    assert ir(None) is None
    assert ir("") is None
    assert ir("BLAH BLAH BLAH") is None


def test_mag_string():
    """Magnitude string for various events"""
    lr = lsr.LSR()
    lr.typetext = "TSTM WND GST"
    lr.magnitude_units = "MPH"
    lr.magnitude_f = 59
    lr.magnitude_qualifier = "M"
    assert lr.mag_string() == "TSTM WND GST of M59 MPH"


def test_get_dbtype():
    """See what we get for a given LSR typetext"""
    lr = lsr.LSR()
    lr.typetext = "TORNADO"
    assert lr.get_dbtype() == "T"


def test_lowercase():
    """Make sure we can properly convert cities to mixed case"""
    assert _mylowercase("1 N AMES") == "1 N Ames"
    assert _mylowercase("1 NNW AMES") == "1 NNW Ames"
