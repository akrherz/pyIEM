"""Testing of pyiem.autoplot"""

from datetime import date, datetime

import pytest

from pyiem.autoplot import get_autoplot_context
from pyiem.exceptions import IncompleteWebRequest, UnknownStationException


def test_get_autoplot_context_alias():
    """Test that an alias can be used."""
    form = {"blah": ""}
    cfg = {
        "arguments": [
            {
                "type": "select",
                "name": "blah",
                "default": "sa",
                "options": {
                    "conus": "hi",
                    "sa": "bye",
                },
                "alias": {
                    "": "conus",
                },
            }
        ]
    }
    ctx = get_autoplot_context(form, cfg)
    assert ctx["blah"] == "conus"


def test_get_autoplot_context_alias_list():
    """Test that an alias can be used."""
    form = {"blah": ["", "two"]}
    cfg = {
        "arguments": [
            {
                "type": "select",
                "name": "blah",
                "default": "sa",
                "multiple": True,
                "options": {
                    "conus": "hi",
                    "sa": "bye",
                    "two": "two",
                },
                "alias": {
                    "": "conus",
                },
            }
        ]
    }
    ctx = get_autoplot_context(form, cfg)
    assert ctx["blah"] == ["conus", "two"]


def test_get_autoplot_context_text_pattern():
    """Test the pattern validation."""
    form = {"rng": "1960"}
    cfg = {
        "arguments": [
            {
                "type": "text",
                "name": "rng",
                "default": "1960-2020",
                "pattern": r"^\d{4}\s*-\s*\d{4}$",
            }
        ]
    }
    ctx = get_autoplot_context(form, cfg)
    assert ctx["rng"] == cfg["arguments"][0]["default"]


def test_get_autoplot_context_bad_float():
    """Test that we handle bad floats."""
    form = {"thres": "Qq"}
    for typ in ["int", "float"]:
        cfg = {"arguments": [{"type": typ, "name": "thres", "default": 100}]}
        with pytest.raises(IncompleteWebRequest):
            get_autoplot_context(form, cfg)


def test_get_autoplot_context_lowercase_state():
    """A lowercase state should not be permitted!"""
    form = {"state": "Qq"}
    cfg = {"arguments": [{"type": "state", "name": "state", "default": "MN"}]}
    ctx = get_autoplot_context(form, cfg)
    assert ctx["state"] == "MN"


def test_gh709_get_autoplot_context_cmap():
    """Test that we handle invalid cmaps."""
    form = {"c": "bah"}
    cfg = {"arguments": [{"type": "cmap", "name": "c", "default": "jet"}]}
    ctx = get_autoplot_context(form, cfg)
    assert ctx["c"] == "jet"


def test_gh709_get_autoplot_context_cmap_valid():
    """Test that we handle invalid cmaps."""
    form = {"c": "viridis_r"}
    cfg = {"arguments": [{"type": "cmap", "name": "c", "default": "jet"}]}
    ctx = get_autoplot_context(form, cfg)
    assert ctx["c"] == form["c"]


def test_get_autoplot_context_e_set():
    """Ensure that _e gets set."""
    form = {"_e": "apdiv"}
    cfg = {"arguments": []}
    ctx = get_autoplot_context(form, cfg)
    assert ctx["_e"] == form["_e"]


def test_get_autoplot_context_no_r_set():
    """Ensure that _r gets set when not provided by the form."""
    form = {"dpi": 100}
    cfg = {"arguments": [], "defaults": {"_r": "88"}}
    ctx = get_autoplot_context(form, cfg)
    assert ctx["_r"] == "88"


def test_get_autoplot_context_internal():
    """Test that internal hacks are handled within autoplot."""
    form = {}
    cfg = {"arguments": []}
    ctx = get_autoplot_context(form, cfg)
    assert "dpi" not in ctx
    form["_r"] = "43"
    ctx = get_autoplot_context(form, cfg)
    assert "_r" in ctx


def test_get_apctx_sday():
    """Test the sday type."""
    form = {"sdate": "2000-04-05", "edate": "0504"}
    cfg = {
        "arguments": [
            {"type": "sday", "name": "sdate", "max": "1001"},
            {"type": "sday", "name": "edate", "min": "0201"},
            {"type": "sday", "name": "odate", "default": "0210"},
            {"type": "dat", "name": "dat", "default": "Bah"},
        ]
    }
    ctx = get_autoplot_context(form, cfg)
    assert ctx["sdate"] == date(2000, 4, 5)
    assert ctx["edate"] == date(2000, 5, 4)
    assert ctx["odate"] == date(2000, 2, 10)


def test_get_autoplot_wfo():
    """Test the rectification of WFO network troubles."""
    cfg = dict(
        arguments=[dict(type="networkselect", name="cwa", default="DMX")]
    )
    form = dict(cwa="AFG", network="WFO")
    ctx = get_autoplot_context(form, cfg)
    assert ctx["cwa"] == "PAFG"
    form = dict(cwa="SJU", network="WFO")
    ctx = get_autoplot_context(form, cfg)
    assert ctx["cwa"] == "TJSJ"
    form = dict(cwa="XXX", network="WFO")
    with pytest.raises(UnknownStationException):
        get_autoplot_context(form, cfg)


def test_get_autoplot_context_name():
    """Test the helper provides a nice name for us."""
    form = dict(station="_ZZZ", network="ZZ_ASOS")
    cfg = dict(
        arguments=[dict(type="station", name="station", default="_ZZZ")]
    )
    ctx = get_autoplot_context(form, cfg)
    assert ctx["_sname"] == "[_ZZZ] ((_ZZZ))"


def test_get_autoplot_context_network():
    """Do we handle network issues OK."""
    form = dict(station="ZZZ", network="ZZ_ASOS")
    cfg = dict(
        arguments=[dict(type="station", name="station", default="IA0000")]
    )
    with pytest.raises(UnknownStationException):
        get_autoplot_context(form, cfg)


def test_apctx_empty_datetime():
    """Test this edge case."""
    form = {
        "d": "",
    }
    opts = {
        "arguments": [
            {"type": "datetime", "name": "d", "default": "2011/11/12+0000"},
        ]
    }
    res = get_autoplot_context(form, opts, rectify_dates=True)
    assert res["d"] == datetime(2011, 11, 12)


def test_apctx_datetime():
    """Test some edge cases."""
    form = {
        "d": "2016-06-31",
        "d2": "2016-09-A1 1314",
    }
    opts = {
        "arguments": [
            {"type": "datetime", "name": "d", "default": "2011/11/12 0000"},
            {"type": "datetime", "name": "d2", "default": "2011/11/12 1213"},
        ]
    }
    with pytest.raises(ValueError):
        get_autoplot_context(form, opts, rectify_dates=True)


def test_get_autoplot_context_dates():
    """Test how we deal with all kinds of date cruft."""
    form = {
        "d": "2016-06-31",
        "d2": "2016-09-31+1314",
        "d3": "2016-09-301314",
    }
    opts = dict(
        arguments=[
            {
                "type": "date",
                "name": "d",
                "default": "2011/11/12",
                "max": "2022/01/01",
                "min": "2011/01/01",
            },
            dict(type="datetime", name="d2", default="2011/11/12 1213"),
            {"type": "datetime", "name": "d3", "default": "2011/11/12 1213"},
        ]
    )
    ctx = get_autoplot_context(form, opts, rectify_dates=True)
    assert ctx["d"] == date(2016, 6, 30)
    assert ctx["d2"] == datetime(2016, 9, 30, 13, 14)
    assert ctx["d3"] == datetime(2016, 9, 30, 13, 14)
    form["d"] = "2016-06-30"
    with pytest.raises(IncompleteWebRequest):
        get_autoplot_context(form, opts, rectify_dates=False)

    form["d"] = "2016-06-XX"
    with pytest.raises(IncompleteWebRequest):
        get_autoplot_context(form, opts, rectify_dates=False)

    form["d"] = "2016-06-31"
    form["d2"] = "2016-09-30"  # triggers appending 0000
    with pytest.raises(IncompleteWebRequest):
        get_autoplot_context(form, opts, rectify_dates=False)

    form["d"] = "2016-06-30"
    form["d2"] = "2016-09-30 2414"
    with pytest.raises(IncompleteWebRequest):
        get_autoplot_context(form, opts, rectify_dates=False)


def test_get_autoplot_context_optional():
    """Test that we require the optional flag nomenclature."""
    form = dict(year=2011)
    opts = dict(
        arguments=[
            dict(type="year", name="year", optional=True, default=2012),
        ]
    )
    ctx = get_autoplot_context(form, opts, enforce_optional=True)
    assert "year" not in ctx


def test_get_autoplot_context():
    """See that we can do things."""
    form = dict(
        type2="bogus", t="15.0", type3=["max-high", "bogus", "min-high"]
    )
    form["type"] = "max-low"
    pdict = {
        "max-high": "Maximum High",
        "avg-high": "Average High",
        "min-high": "Minimum High",
        "max-low": "Maximum Low",
    }
    cfg = dict(
        arguments=[
            dict(
                type="select", name="type", default="max-high", options=pdict
            ),
            dict(
                type="select", name="type2", default="max-high", options=pdict
            ),
            dict(
                type="select",
                name="type3",
                default="max-high",
                options=pdict,
                multiple=True,
            ),
            dict(
                type="select",
                name="type4",
                default="max-high",
                options=pdict,
                multiple=True,
                optional=True,
            ),
            dict(
                type="select", name="type5", default="max-high", options=pdict
            ),
            dict(type="int", name="threshold", default="-99.0"),
            dict(type="int", name="t", default=9, min=0, max=10),
            dict(type="date", name="d", default="2011/11/12"),
            dict(
                type="datetime",
                name="d2",
                default="2011/11/12 0000",
                max="2017/12/12 1212",
                min="2011/01/01 0000",
            ),
            dict(type="year", name="year", default="2011", optional=True),
            dict(type="float", name="f", default=1.10),
        ]
    )
    ctx = get_autoplot_context(form, cfg)
    assert isinstance(ctx["threshold"], int)
    assert ctx["type"] == "max-low"
    assert ctx["type2"] == "max-high"
    assert isinstance(ctx["f"], float)
    assert ctx["t"] == 9
    assert ctx["d"] == date(2011, 11, 12)
    assert ctx["d2"] == datetime(2011, 11, 12)
    assert "year" not in ctx
    assert "bogus" not in ctx["type3"]
    assert "type4" not in ctx


def test_vtecps():
    """Can we properly handle the vtecps form type"""
    cfg = dict(
        arguments=[
            dict(
                type="vtec_ps",
                name="v1",
                default="TO.W",
                label="VTEC Phenomena and Significance 1",
            ),
            dict(
                type="vtec_ps",
                name="v2",
                default="TO.A",
                optional=True,
                label="VTEC Phenomena and Significance 2",
            ),
            dict(
                type="vtec_ps",
                name="v3",
                default=None,
                optional=True,
                label="VTEC Phenomena and Significance 3",
            ),
            dict(
                type="vtec_ps",
                name="v4",
                default="FL.Y",
                optional=True,
                label="VTEC Phenomena and Significance 4",
            ),
            dict(
                type="vtec_ps",
                name="v5",
                default="UNUSED",
                optional=True,
                label="VTEC Phenomena and Significance 5",
            ),
            dict(
                type="vtec_ps",
                name="v6",
                default="UNUSED",
                optional=True,
                label="VTEC Phenomena and Significance 6",
            ),
        ]
    )
    form = dict(
        phenomenav1="SV",
        significancev1="A",
        _opt_v4="on",
        phenomenav4="TO",
        significancev4="W",
        phenomenav6="",
        significancev6=None,
    )
    ctx = get_autoplot_context(form, cfg)
    # For v1, we were explicitly provided by from the form
    assert ctx["phenomenav1"] == "SV"
    assert ctx["significancev1"] == "A"
    # For v2, optional is on, so our values should be None
    assert ctx.get("phenomenav2") is None
    # For v3, should be None as well
    assert ctx.get("phenomenav3") is None
    # For v4, we provided a value via form
    assert ctx["significancev4"] == "W"
    # For v5, we have a bad default set
    assert ctx.get("phenomenav5") is None
    # For v6, we have empty strings, so should be None
    assert ctx.get("phenomenav6") is None
    # Test empty strings
    form["phenomenav1"] = ""
    form["significancev1"] = ""
    ctx = get_autoplot_context(form, cfg)
    assert ctx["phenomenav1"] == "TO"
    assert ctx["significancev1"] == "W"
