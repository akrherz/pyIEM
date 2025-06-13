"""Test coverage for our jinja2 templates."""

from pyiem.templates.iem import TEMPLATE, get_template


def test_appmode():
    """Test that appmode disables global CSS/JS from being included."""
    res = TEMPLATE.render({"appmode": True})
    assert "font-awesome" not in res
    assert "iastate-iem.js" not in res


def test_basic_usage():
    """Test that we can import what we think we can."""
    res = TEMPLATE.render()
    assert res is not None


def test_get_template():
    """See that we can load other templates."""
    tpl = get_template("app.j2")
    assert tpl is not None
