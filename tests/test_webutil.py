"""Tests for webutil.py"""
from zoneinfo import ZoneInfo

import mock
import pytest
from pyiem.database import get_dbconn
from pyiem.exceptions import (
    BadWebRequest,
    IncompleteWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
from pyiem.webutil import (
    TELEMETRY,
    _add_to_queue,
    add_to_environ,
    ensure_list,
    iemapp,
)


def test_disable_parse_times():
    """Test that we can disable parsing times."""
    form = {
        "sts": "2023-09-11 1212",
    }
    environ = {}
    add_to_environ(environ, form, parse_times=False)
    assert environ["sts"] == form["sts"]


def test_add_telemetry():
    """Test adding something to the queue."""
    _add_to_queue(
        TELEMETRY(
            timing=1,
            status_code=200,
            client_addr="",
            app="test",
            request_uri="",
        )
    )


def test_ensure_list():
    """Test that we get lists!"""
    assert ensure_list({}, "a") == []
    assert ensure_list({"a": "b"}, "a") == ["b"]
    assert ensure_list({"a": ["b"]}, "a") == ["b"]


def test_iemapp_iemdb_cursor():
    """Test with a cursor set."""

    @iemapp(iemdb="mesosite", iemdb_cursorname="magic")
    def application(environ, _start_response):
        """Test."""
        environ["iemdb.mesosite.cursor"].execute("SELECT 1 as test")
        assert environ["iemdb.mesosite.cursor"].rowcount == -1
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "year=2021&year=2021&month1=2&day1=3",
    }
    sr = mock.MagicMock()
    application(env, sr)
    # ensure that the connection was closed
    assert env["iemdb.mesosite.conn"].closed


def test_iemapp_iemdb():
    """Test the request of a database connection."""

    @iemapp(iemdb=["mesosite", "postgis"])
    def application(environ, _start_response):
        """Test."""
        environ["iemdb.mesosite.cursor"].execute("SELECT 1 as test")
        environ["iemdb.postgis.cursor"].execute("SELECT 1 as test")
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "year=2021&year=2021&month1=2&day1=3",
    }
    sr = mock.MagicMock()
    application(env, sr)
    # ensure that the connection was closed
    assert env["iemdb.mesosite.conn"].closed
    assert env["iemdb.postgis.conn"].closed


def test_duplicated_year_in_form():
    """Test the forgiveness."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "year=2021&year=2021&month1=2&day1=3",
    }
    sr = mock.MagicMock()
    application(env, sr)
    assert env["sts"].year == 2021


def test_forgive_duplicate_tz():
    """Test the forgiveness of this combo."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "tz=etc/utc&tz=etc/utc",
    }
    sr = mock.MagicMock()
    assert application(env, sr)[0].decode("ascii").find("Hello!") > -1


def test_duplicated_tz_in_form():
    """Test that this is handled."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "tz=etc/utc&tz=etc/UTC",
    }
    sr = mock.MagicMock()
    assert application(env, sr)[0].decode("ascii").find("twice") > -1


def test_forgive_feb29():
    """Test that this is not rectified."""
    form = {
        "day1": "30",
        "month1": "2",
        "year1": "2020",
        "day2": "32",
        "month2": "2",
        "year2": "2021",
    }
    environ = {}
    add_to_environ(environ, form)
    assert environ["sts"].day == 29
    assert environ["ets"].day == 28


def test_forgive_bad_day_of_month():
    """Test forgiveness of specifying a bad day of month."""
    form = {
        "day1": "30",
        "month1": "2",
        "year1": "2021",
        "day2": "31",
        "month2": "6",
        "year2": "2021",
    }
    environ = {}
    add_to_environ(environ, form)
    assert environ["sts"].day == 28
    assert environ["ets"].day == 30


def test_badrequest_raises():
    """Test that this hits the XSS."""
    form = {"a": "<script>"}
    with pytest.raises(BadWebRequest):
        add_to_environ({}, form)


def test_badrequest_raises_list():
    """Test that this hits the XSS."""
    form = {"a": ["<script>", "b"]}
    with pytest.raises(BadWebRequest):
        add_to_environ({}, form)


def test_sts_not_a_timestamp():
    """Test that we ignore sts and ets when not a datetime."""
    form = {
        "sts": "2023-10-13T12:30:00.000Z",
        "ets": "AMSI4",
    }
    environ = {}
    add_to_environ(environ, form)
    assert environ["sts"].year == 2023
    assert environ["ets"] == form["ets"]


def test_add_to_environ_badtimes():
    """Test the handling of these problems."""
    form = {
        "tz": "Rolly/Polley",
        "year1": "2023",
        "month1": "2",
        "day1": "30",
        "hour1": "12",
        "minute1": "30",
    }
    environ = {}
    with pytest.raises(IncompleteWebRequest):
        add_to_environ(environ, form)
    environ = {}
    form["tz"] = "America/Chicago"
    form["day1"] = "sknt31"
    with pytest.raises(IncompleteWebRequest):
        add_to_environ(environ, form)


def test_add_to_environ_tstrings():
    """Test strings in various formats."""
    form = {
        "sts": "2023-10-13T12:30:00.000Z",
        "ets": "2023-10-13 12:30",
    }
    environ = {}
    add_to_environ(environ, form)
    assert environ["sts"].year == 2023
    assert environ["sts"].tzinfo == ZoneInfo("UTC")
    assert environ["ets"].year == 2023
    assert environ["ets"].tzinfo == ZoneInfo("America/Chicago")


def test_add_to_environ():
    """Test adding things to the context."""
    form = {
        "day1": "2",
        "month1": "2",
        "year1": "2021",
        "hour1": "12",
        "minute1": "30",
        "blah": ["one", "two"],
    }
    for key in list(form):
        form[key.replace("1", "2")] = form[key]
    environ = {"day1": None}
    with pytest.warns(UserWarning):
        add_to_environ(environ, form)
    assert environ["sts"].year == 2021
    assert environ["sts"].hour == 12
    assert environ["sts"].minute == 30
    assert environ["ets"].year == 2021


def test_incomplete():
    """Test that the IncompleteWebRequest runs."""
    msg = "HELLO WORLD"

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise IncompleteWebRequest(msg)

    env = {
        "wsgi.input": mock.MagicMock(),
    }
    sr = mock.MagicMock()
    assert application(env, sr)[0].decode("ascii").find(msg) > -1


def test_newdatabase():
    """Test that the NewDatabaseConnectionError runs."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise NewDatabaseConnectionFailure()

    env = {
        "wsgi.input": mock.MagicMock(),
    }
    sr = mock.MagicMock()
    assert application(env, sr)[0].decode("ascii").find("akrherz") > -1


def test_nodatafound():
    """Test that the NoDataFound runs."""
    res = "Magic"

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise NoDataFound(res)

    env = {
        "wsgi.input": mock.MagicMock(),
    }
    sr = mock.MagicMock()
    assert application(env, sr)[0].decode("ascii") == res


def test_xss():
    """Test that the XSS runs."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise BadWebRequest("This is a test")

    env = {
        "wsgi.input": mock.MagicMock(),
    }
    sr = mock.MagicMock()
    assert application(env, sr)[0].decode("ascii").find("akrherz") > -1


def test_iemapp_decorator():
    """Try the API."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {"wsgi.input": mock.MagicMock()}
    assert application(env, None) == [b"Content-type: text/plain\n\nHello!"]


def test_typoed_tz():
    """Test that we handle when a tz gets commonly typoed."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "tz=etc/utc&sts=2021-01-01T00:00",
    }
    assert application(env, None) == [b"Content-type: text/plain\n\nHello!"]


def test_iemapp_raises_newdatabaseconnectionfailure():
    """This should nicely catch a raised exception."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        get_dbconn("this will fail")
        return [b"Content-type: text/plain\n\nHello!"]

    # mock a start_response function
    sr = mock.MagicMock()
    assert application({}, sr)[0].decode("ascii").find("akrherz") > -1


def test_iemapp_catches_vanilla_exception():
    """This should nicely catch a raised exception."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise Exception("This is a test")

    # mock a start_response function
    sr = mock.MagicMock()
    assert application({}, sr)[0].decode("ascii").find("akrherz") > -1
