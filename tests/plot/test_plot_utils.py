"""Test pyiem.plot.utils."""

from pyiem.plot.util import fitbox, draw_logo


def test_none_fitbox():
    """Test that we can give fitbox a None value."""
    assert fitbox(None, None, 0, 1, 2, 3) is None


def test_none_drawlogo():
    """Test that nothing happens when we pass a None logo."""
    assert draw_logo(None, None) is None
