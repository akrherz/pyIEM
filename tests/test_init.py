"""Test pyiem module level stuff."""
import pyiem
import pytest


def test_version():
    """Test that version works."""
    assert pyiem.__version__


def test_badattr():
    """Test that we can't access bad attributes."""
    with pytest.raises(AttributeError):
        pyiem.bogus
