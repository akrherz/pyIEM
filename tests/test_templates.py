"""Test coverage for our jinja2 templates."""

from pyiem.templates import get_site_template


def test_appmode():
    """Test that appmode disables global CSS/JS from being included."""
    res = get_site_template("iem", "full.j2").render({"appmode": True})
    assert "font-awesome" not in res
    assert "iastate-iem.js" not in res


def test_basic_usage():
    """Test that we can import what we think we can."""
    res = get_site_template("iem", "full.j2").render()
    assert res is not None


def test_get_template():
    """See that we can load other templates."""
    tpl = get_site_template("iem", "app.j2")
    assert tpl is not None


def test_dep_template():
    """Test that we get back something for the DEP template."""
    res = get_site_template("dep", "full.j2").render({})
    assert "Daily Erosion Project" in res
