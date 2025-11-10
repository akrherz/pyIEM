"""Test SHEF Model."""
# pylint: disable=redefined-outer-name

import pytest

from pyiem.models.shef import SHEFElement
from pyiem.util import utc


@pytest.fixture
def elem() -> SHEFElement:
    """Return an empty SHEFElement."""
    return SHEFElement(station="NA", basevalid=utc(), valid=utc())


def test_simple(elem):
    """Test that we can walk."""
    elem.consume_code("TAIRZ")
    assert elem.physical_element == "TA"


def test_d(elem):
    """Test that we do not allow D physical_codes."""
    with pytest.raises(ValueError):
        elem.consume_code("DA")


def test_sevenchar(elem):
    """Test that we can consume a seven char code."""
    elem.consume_code("QRHRZXA")
    assert elem.probability == "A"


def test_lonlat(elem):
    """Test that we can process stranger locations."""
    elem.station = "X3080995"
    res = elem.lonlat()
    assert abs(res[0] - -99.5) < 0.01
    assert abs(res[1] - 30.8) < 0.01

    elem.station = "W3080995"
    res = elem.lonlat()
    assert abs(res[0] - -99.5) < 0.01
    assert abs(res[1] - -30.8) < 0.01

    elem.station = "W308099"
    res = elem.lonlat()
    assert res[0] is None


def test_varname(elem):
    """Test the varname conversion."""
    assert elem.varname() is None
    elem.consume_code("TAI")
    assert elem.varname() == "TAIRZZZ"


def test_unit_conversion(elem):
    """Test that we can convert units."""
    elem.num_value = 100
    elem.unit_convention = "S"
    elem.physical_element = "TA"
    assert abs(elem.to_english() - 212) < 0.01

    # Unknown conversion yields back original value
    elem.physical_element = "--"
    assert abs(elem.to_english() - 100) < 0.01

    elem.unit_convention = "E"
    assert abs(elem.to_english() - 100) < 0.01
