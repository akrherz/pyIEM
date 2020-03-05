"""Test coverage for our jinja2 templates."""

from pyiem.templates.iem import TEMPLATE


def test_basic_usage():
    """Test that we can import what we think we can."""
    res = TEMPLATE.render()
    assert res is not None
