"""Test pyiem.plot.utils."""

import pytest
from pyiem.plot.util import centered_bins, draw_logo, fitbox, pretty_bins


def test_pretty_bins_large_value():
    """Test a value larger than we can support."""
    with pytest.raises(ValueError) as exc_info:
        pretty_bins(-1e9, 1e9)
    assert exc_info.match("^step:")


def test_gh665_pretty_bins_index_error():
    """Test that this works."""
    a = pretty_bins(21.5, 9886.5)
    assert abs(a[0] - 0) < 0.01


def test_pretty_bins():
    """Test that we get nice pretty bins!"""
    a = pretty_bins(-1, 10)
    assert abs(a[-1] - 10.0) < 0.01


def test_centered_bins_orig():
    """See that we can compute some nice centered bins"""
    a = centered_bins(10)
    assert a[0] == -10
    a = centered_bins(55)
    assert a[0] == -75
    a = centered_bins(99)
    assert a[0] == -100
    a = centered_bins(99, bins=9)
    assert a[0] == -100
    a = centered_bins(100, on=100)
    assert a[0] == 0
    a = centered_bins(0.9)
    assert abs(a[-1] - 1.0) < 0.001
    a = centered_bins(1.2888)
    assert abs(a[-1] - 1.5) < 0.001


def test_centered_bins():
    """Test that we get what we want from centered bins."""
    res = centered_bins(10, 0, 6)  # actually get back 5 bins
    assert abs(res[0] - -10) < 0.01
    assert abs(res[2] - 0) < 0.01
    assert abs(res[-1] - 10) < 0.01


def test_none_fitbox():
    """Test that we can give fitbox a None value."""
    assert fitbox(None, None, 0, 1, 2, 3) is None


def test_none_drawlogo():
    """Test that nothing happens when we pass a None logo."""
    assert draw_logo(None, None) is None
