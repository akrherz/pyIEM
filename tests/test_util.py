"""Testing of util."""
# pylint: disable=redefined-outer-name
import datetime
from datetime import timezone
import string
import random
import tempfile
from io import BytesIO
from collections import OrderedDict
import mock

# third party
import pytest
import numpy as np
import psycopg2
from pyiem import util
from pyiem.exceptions import NoDataFound


@pytest.fixture
def cursor():
    """Return a database cursor."""
    return util.get_dbconn("mesosite").cursor()


def test_get_sqlalchemy():
    """Test that we can do a contextmanager with this API."""
    with util.get_sqlalchemy_conn("coop") as conn:
        assert conn is not None


def test_insert_nan(cursor):
    """Test that we properly insert NaN values as nulls."""
    vals = np.array([0, np.nan, 10], dtype=np.float64)
    cursor.execute(
        "INSERT into stations(iemid, remote_id) VALUES (%s, %s) "
        "RETURNING remote_id",
        (-100, vals[1]),
    )
    assert cursor.fetchone()[0] is None


def test_web2ldm():
    """Test that we can ingest something and insert it."""
    assert util.web2ldm(
        "http://mesonet.agron.iastate.edu/robots.txt",
        str(util.utc()),
        md5_from_name=True,
        pqinsert="true",
    )


def test_web2ldm_dup():
    """Test that we fail when inserting a duplicate."""
    pqstr = str(util.utc())
    util.web2ldm(
        "http://mesonet.agron.iastate.edu/robots.txt",
        pqstr,
        md5_from_name=True,
    )
    assert not util.web2ldm(
        "http://mesonet.agron.iastate.edu/robots.txt",
        pqstr,
        md5_from_name=True,
    )


def test_web2ldm_failed():
    """Test for graceful failure when pqinsert fails."""
    assert not util.web2ldm(
        "http://mesonet.agron.iastate.edu/robots.txt",
        "Blah",
        md5_from_name=True,
        pqinsert="cat",
    )


def test_web2ldm_badurl():
    """Test for graceful failure when given a URL that will 404."""
    assert not util.web2ldm(
        "http://iastate.edu/not_existing",
        "Blah",
    )


def test_invalid_file():
    """Test that we don't error out on an invalid filename."""
    assert util.load_geodf("this shall not work").empty


@pytest.mark.parametrize("dbname", ["mos", "hads", "iemre", "postgis"])
def test_get_dbconn(dbname):  # noqa
    """Does our code work for various database names."""
    pgconn = util.get_dbconn(dbname)
    assert pgconn is not None


def test_c2f_singleton():
    """Test that we get back a singleton when providing one."""
    assert abs(util.c2f(0) - 32) < 0.01


def test_c2f_list():
    """Test that we get back a list when providing one."""
    assert abs(util.c2f([0])[0] - 32) < 0.01


def test_c2f_masked_array():
    """Test that we get back a masked array."""
    val = np.ma.masked_array([0, 0], mask=[True, False])
    res = util.c2f(val)
    assert res[0].mask
    assert not np.ma.is_masked(res[1])


def test_mm2inch():
    """Test conversion of mm value to inch."""
    assert abs(util.mm2inch(25.4) - 1) < 0.01


def test_get_dbconn_bad():
    """Test that we raise a warning."""
    with pytest.warns(UserWarning, match="database connection failure"):
        with pytest.raises(psycopg2.OperationalError):
            util.get_dbconn("bogus")


def test_get_dbconn_failover():
    """See if failover works?"""
    with pytest.warns(UserWarning, match="database connection failure"):
        with pytest.raises(psycopg2.OperationalError):
            util.get_dbconn("mesosite", host="b")


def test_escape():
    """Does escaping work?"""
    res = util.html_escape("Hello THERE!</p>")
    assert res == "Hello THERE!&lt;/p&gt;"


def test_ncopen_conflict():
    """Test what happens when we get a conflict."""
    with tempfile.NamedTemporaryFile() as tmp:
        nc = util.ncopen(tmp.name, mode="w")
        nc.title = "hello"
        nc.close()
        nc = util.ncopen(tmp.name, "r")
        nc2 = util.ncopen(tmp.name, "w", timeout=5)
        assert nc2 is None


def test_ncopen():
    """Does ncopen at least somewhat work."""
    with pytest.raises(IOError):
        util.ncopen("/tmp/bogus.nc")


def test_logger(caplog):
    """Can we emit logs."""
    log = util.logger()
    log.warning("hi daryl")
    assert "hi daryl" in caplog.text


def test_logger_no(caplog):
    """Can we not emit logs."""
    util.LOG.debug("hi daryl")
    assert "hi daryl" not in caplog.text


def test_find_ij():
    """Can we find_ij()."""
    xgrid, ygrid = np.meshgrid(np.arange(10), np.arange(10))
    i, j = util.find_ij(xgrid, ygrid, 4, 4)
    assert i == 4
    assert j == 4


def test_ssw():
    """Does pyiem.util.ssw work?"""
    with mock.patch("sys.stdout", new=BytesIO()) as fake_out:
        util.ssw("Hello Daryl!")
        assert fake_out.getvalue() == b"Hello Daryl!"
        fake_out.seek(0)
        util.ssw(b"Hello Daryl!")
        assert fake_out.getvalue() == b"Hello Daryl!"
        fake_out.seek(0)


def test_utc():
    """Does the utc() function work as expected."""
    answer = datetime.datetime(2017, 2, 1, 2, 20).replace(tzinfo=timezone.utc)
    res = util.utc(2017, 2, 1, 2, 20)
    assert answer == res
    answer = datetime.datetime.utcnow().replace(tzinfo=timezone.utc)
    assert answer.year == util.utc().year


def test_get_autoplot_context_no_r_set():
    """Ensure that _r gets set when not provided by the form."""
    form = {}
    cfg = {"arguments": [], "defaults": {"_r": "88"}}
    ctx = util.get_autoplot_context(form, cfg)
    assert ctx["_r"] == "88"


def test_get_autoplot_context_internal():
    """Test that internal hacks are handled within autoplot."""
    form = {}
    cfg = {"arguments": []}
    ctx = util.get_autoplot_context(form, cfg)
    assert "dpi" not in ctx
    form["_r"] = "43"
    ctx = util.get_autoplot_context(form, cfg)
    assert "_r" in ctx


def test_get_autoplot_context_name():
    """Test the helper provides a nice name for us."""
    form = dict(station="_ZZZ", network="ZZ_ASOS")
    cfg = dict(
        arguments=[dict(type="station", name="station", default="_ZZZ")]
    )
    ctx = util.get_autoplot_context(form, cfg)
    assert ctx["_sname"] == "[_ZZZ] ((_ZZZ))"


def test_get_autoplot_context_network():
    """Do we handle network issues OK."""
    form = dict(station="ZZZ", network="ZZ_ASOS")
    cfg = dict(
        arguments=[dict(type="station", name="station", default="IA0000")]
    )
    with pytest.raises(NoDataFound):
        util.get_autoplot_context(form, cfg)


def test_get_autoplot_context_dates():
    """Test how we deal with all kinds of date cruft."""
    form = {
        "d": "2016-06-31",
        "d2": "2016-09-31 1314",
    }
    opts = dict(
        arguments=[
            dict(
                type="date",
                name="d",
                default="2011/11/12",
                maxval="2022/01/01",
            ),
            dict(type="datetime", name="d2", default="2011/11/12 1213"),
        ]
    )
    ctx = util.get_autoplot_context(form, opts, rectify_dates=True)
    assert ctx["d"] == datetime.date(2016, 6, 30)
    assert ctx["d2"] == datetime.datetime(2016, 9, 30, 13, 14)
    form["d"] = "2016-06-30"
    with pytest.raises(ValueError):
        util.get_autoplot_context(form, opts, rectify_dates=False)

    form["d"] = "2016-06-31"
    form["d2"] = "2016-09-30"  # triggers appending 0000
    with pytest.raises(ValueError):
        util.get_autoplot_context(form, opts, rectify_dates=False)

    form["d"] = "2016-06-30"
    form["d2"] = "2016-09-30 2414"
    with pytest.raises(ValueError):
        util.get_autoplot_context(form, opts, rectify_dates=False)


def test_get_autoplot_context_optional():
    """Test that we require the optional flag nomenclature."""
    form = dict(year=2011)
    opts = dict(
        arguments=[
            dict(type="year", name="year", optional=True, default=2012),
        ]
    )
    ctx = util.get_autoplot_context(form, opts, enforce_optional=True)
    assert "year" not in ctx


def test_get_autoplot_context():
    """See that we can do things."""
    form = dict(type2="bogus", t=15, type3=["max-high", "bogus", "min-high"])
    form["type"] = "max-low"
    pdict = OrderedDict(
        [
            ("max-high", "Maximum High"),
            ("avg-high", "Average High"),
            ("min-high", "Minimum High"),
            ("max-low", "Maximum Low"),
        ]
    )
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
            dict(type="int", name="threshold", default=-99),
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
    ctx = util.get_autoplot_context(form, cfg)
    assert isinstance(ctx["threshold"], int)
    assert ctx["type"] == "max-low"
    assert ctx["type2"] == "max-high"
    assert isinstance(ctx["f"], float)
    assert ctx["t"] == 9
    assert ctx["d"] == datetime.date(2011, 11, 12)
    assert ctx["d2"] == datetime.datetime(2011, 11, 12)
    assert "year" not in ctx
    assert "bogus" not in ctx["type3"]
    assert "type4" not in ctx


def test_backoff():
    """Do the backoff of a bad func"""

    def bad():
        """Always errors"""
        raise Exception("Always Raises :)")

    res = util.exponential_backoff(bad, _ebfactor=0)
    assert res is None


def test_grid_bounds():
    """Can we compute grid bounds correctly"""
    lons = np.arange(-100, -80, 0.1)
    lats = np.arange(29, 51, 0.2)
    (x0, y0, x1, y1) = util.grid_bounds(lons, lats, [-96, 32, -89, 40])
    assert x0 == 41
    assert x1 == 111
    assert y0 == 16
    assert y1 == 56
    (lons, lats) = np.meshgrid(lons, lats)
    (x0, y0, x1, y1) = util.grid_bounds(lons, lats, [-96, 32, -89, 40])
    assert x0 == 40
    assert x1 == 110
    assert y0 == 15
    assert y1 == 55


def test_noaaport_text_cruft_at_top():
    """Test that we properly remove empty lines at the top."""
    data = "\r\r\r\n\r\n\r\r\r\r\r\n" + util.get_test_file("WCN.txt")
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n098 \r\r\n"


def test_noaaport_text_no_ldm_sequence():
    """Test that we deal with not having an LDM sequence number."""
    data = "AAAAAA\r\r\n" + util.get_test_file("WCN.txt")
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n000 \r\r\n"


def test_noaaport_text():
    """See that we do what we expect with noaaport text processing"""
    data = util.get_test_file("WCN.txt")
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n098 \r\r\n"
    assert res[-9:] == "SMALL\r\r\n\003"


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
        ]
    )
    form = dict(
        phenomenav1="SV",
        significancev1="A",
        _opt_v4="on",
        phenomenav4="TO",
        significancev4="W",
    )
    ctx = util.get_autoplot_context(form, cfg)
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


def test_properties_nocursor():
    """Test that a cursor is generated when necessary."""
    props = util.get_properties()
    assert isinstance(props, dict)


def test_properties(cursor):
    """Try the properties function"""
    tmpname = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    tmpval = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    cursor.execute(
        "INSERT into properties(propname, propvalue) VALUES (%s, %s)",
        (tmpname, tmpval),
    )
    prop = util.get_properties(cursor)
    assert isinstance(prop, dict)
    assert prop[tmpname] == tmpval


def test_drct2text():
    """Test conversion of drct2text"""
    assert util.drct2text(360) == "N"
    assert util.drct2text(90) == "E"
    assert util.drct2text(None) is None
    assert util.drct2text(400) is None
    # A hack to get move coverage
    for i in range(360):
        util.drct2text(i)
