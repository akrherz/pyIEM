"""Test SHEF Model."""
# pylint: disable=redefined-outer-name

import pytest
from pyiem.models.shef import SHEFElement
from pyiem.util import utc


@pytest.fixture
def elem() -> SHEFElement:
    """Return an empty SHEFElement."""
    return SHEFElement(station="NA", valid=utc())


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
