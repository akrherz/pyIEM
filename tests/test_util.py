"""Testing of util."""

# pylint: disable=redefined-outer-name
import logging
import os
import random
import string
import tempfile
from datetime import datetime, timezone
from io import BytesIO

import mock
import numpy as np

# third party
import pytest

from pyiem import util
from pyiem.reference import ISO8601


def test_deprecated_database():
    """Test that we get a DeprecationWarning"""
    with pytest.warns(DeprecationWarning):
        database = util.get_dbconn("mesosite")
        assert database is not None


def test_logger_level():
    """That that we get the right logger level when running a tty."""
    # Mock sys.stdout.isatty
    with mock.patch("sys.stdout.isatty", return_value=True):
        log = util.logger()
        assert log.level == logging.INFO


def test_archive_fetch_localfile_exists():
    """Test what happens when the local file does exist."""
    with (
        tempfile.NamedTemporaryFile() as tmp,
        util.archive_fetch(tmp.name, localdir="/") as ctx,
    ):
        assert ctx == tmp.name


def test_archive_fetch_invalid_remote():
    """Test what happens when the remote file does not exist."""
    with util.archive_fetch("pyiem_testing_doesnotexist") as ctx:
        assert ctx is None


def test_archive_fetch_invalid_remote_head():
    """Test what happens when the remote file does not exist."""
    with util.archive_fetch(
        "pyiem_testing_doesnotexist", method="head"
    ) as ctx:
        assert ctx is None


def test_archive_fetch_head():
    """Test what happens when the remote file does exist."""
    with util.archive_fetch(
        "2024/02/09/mesonet_1200.gif", method="head"
    ) as ctx:
        assert ctx == ""


def test_archive_fetch_remote_exists():
    """Test what happens when the remote file does exist."""
    with util.archive_fetch("2024/02/09/mesonet_1200.gif") as ctx:
        assert ctx.endswith(".gif")
    assert not os.path.isfile(ctx)


@pytest.mark.parametrize("database", ["mesosite"])
def test_insert_nan(dbcursor):
    """Test that we properly insert NaN values as nulls."""
    vals = np.array([0, np.nan, 10], dtype=np.float64)
    dbcursor.execute(
        "INSERT into stations(iemid, remote_id, online) VALUES (%s, %s, 't') "
        "RETURNING remote_id",
        (-100, vals[1]),
    )
    assert dbcursor.fetchone()["remote_id"] is None


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
    assert not util.web2ldm(
        "http://mesonet.agron.iastate.edu/robots.txt",
        pqstr,
        pqinsert="Boghs",
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
        assert nc is not None
        nc2 = util.ncopen(tmp.name, "w", timeout=0.1, _sleep=0.11)
        assert nc2 is None
        nc.close()


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
    answer = datetime(2017, 2, 1, 2, 20).replace(tzinfo=timezone.utc)
    res = util.utc(2017, 2, 1, 2, 20)
    assert answer == res
    answer = datetime.now(timezone.utc)
    assert answer.year == util.utc().year


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
    data = "\r\r\r\n\r\n\r\r\r\r\r\n" + util.get_test_file("WCN/WCN.txt")
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n098 \r\r\n"


def test_noaaport_text_no_ldm_sequence():
    """Test that we deal with not having an LDM sequence number."""
    data = "AAAAAA\r\r\n" + util.get_test_file("WCN/WCN.txt")
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n000 \r\r\n"


def test_noaaport_text():
    """See that we do what we expect with noaaport text processing"""
    data = util.get_test_file("WCN/WCN.txt")
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n098 \r\r\n"
    assert res[-9:] == "SMALL\r\r\n\003"


@pytest.mark.parametrize("database", ["mesosite"])
def test_set_property(dbcursor):
    """Test that we can set a property."""
    util.set_property("test", "test", cursor=dbcursor)
    dbcursor.execute(
        "SELECT propvalue from properties where propname = 'test'"
    )
    assert dbcursor.fetchone()["propvalue"] == "test"
    util.delete_property("test", cursor=dbcursor)
    dbcursor.execute(
        "SELECT propvalue from properties where propname = 'test'"
    )
    assert dbcursor.rowcount == 0


def test_property_datetime_roundtrip():
    """Test that we can roundtrip a datetime."""
    value = util.utc()
    util.set_property("test", value)
    props = util.get_properties()
    assert props["test"] == value.strftime(ISO8601)
    util.delete_property("test")
    props = util.get_properties()
    assert "test" not in props


def test_property_lifecycle():
    """Allow code to create, update, list, and delete properties."""
    rand_propname = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    rand_propval = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    util.set_property(rand_propname, rand_propval)
    props = util.get_properties()
    assert props[rand_propname] == rand_propval
    util.delete_property(rand_propname)
    props = util.get_properties()
    assert rand_propname not in props


def test_properties_nocursor():
    """Test that a cursor is generated when necessary."""
    props = util.get_properties()
    assert isinstance(props, dict)


@pytest.mark.parametrize("database", ["mesosite"])
def test_properties(dbcursor):
    """Try the properties function"""
    tmpname = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    tmpval = "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(7)
    )
    dbcursor.execute(
        "INSERT into properties(propname, propvalue) VALUES (%s, %s)",
        (tmpname, tmpval),
    )
    prop = util.get_properties(dbcursor)
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
