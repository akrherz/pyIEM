"""Test pyiem module level stuff."""
import pyiem


def test_version():
    """Test that version works."""
    assert pyiem.__version__ is not None
