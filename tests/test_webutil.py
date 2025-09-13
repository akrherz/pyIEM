"""Tests for webutil."""

import random
from datetime import datetime
from typing import Optional, Union
from zoneinfo import ZoneInfo

import mock
import pytest
from pydantic import AwareDatetime, Field
from werkzeug.test import Client

from pyiem.database import get_dbconn
from pyiem.exceptions import (
    BadWebRequest,
    IncompleteWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
from pyiem.webutil import (
    TELEMETRY,
    CGIModel,
    ListOrCSVType,
    _is_xss_payload,
    add_to_environ,
    ensure_list,
    iemapp,
    write_telemetry,
)


def test_xss_detect_script_tag():
    assert _is_xss_payload("<script>alert('xss')</script>")


def test_xss_detect_javascript_uri():
    assert _is_xss_payload("javascript:alert(1)")


def test_xss_detect_entity_encoded():
    # Encoded <script> should also be detected after unescape
    assert _is_xss_payload("&lt;script&gt;alert(1)&lt;/script&gt;")


def test_xss_false_positive_simple_text():
    assert not _is_xss_payload("hello world")


def test_xss_false_positive_ampersand():
    # Strings with entities but benign content should not trigger
    assert not _is_xss_payload("Bread &amp; Butter")


def test_allowed_as_list():
    """Test that we don't allow a list in the parsed form."""

    @iemapp(allowed_as_list=["q"])
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return f"{random.random()}"

    c = Client(application)
    resp = c.get("/?q=1&q=2&f=1")
    assert resp.status_code == 200
    resp = c.get("/?q=1&f=2&f=1")
    assert resp.status_code == 422


def test_memcachekey_is_none():
    """Test that we can handle a None memcachekey."""

    @iemapp(memcachekey=lambda _e: None, memcacheexpire=lambda _e: 60)
    def application(_environ, _start_response):
        """Test."""
        return f"aa{random.random()}".encode("ascii")

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "",
    }
    sr = mock.MagicMock()
    res1 = list(application(env, sr))[0]
    assert res1.startswith(b"aa")


def test_iemapp_memcache_keychanged():
    """Test the memcache option."""

    @iemapp(memcachekey=lambda e: f"{random.random()}")
    def application(_environ, _start_response):
        """Test."""
        return f"aa{random.random()}".encode("ascii")

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "",
    }
    sr = mock.MagicMock()
    res1 = list(application(env, sr))[0]
    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "",
    }
    res2 = list(application(env, sr))[0]
    assert res1.startswith(b"aa")
    assert res2.startswith(b"aa")
    assert res1 != res2


def test_iemapp_memcache():
    """Test the memcache option."""

    @iemapp(memcachekey="iem")
    def application(environ, _start_response):
        """Test."""
        return f"{random.random()}"

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "callback=gotData",
    }
    sr = mock.MagicMock()
    res1 = list(application(env, sr))[0]
    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "callback=gotData",
    }
    res2 = list(application(env, sr))[0]
    assert res1.decode("ascii").startswith("gotData")
    assert res1 == res2


def test_iemapp_year_year1():
    """Test that we can handle a legacy situation with DCP app."""

    class MyModel(CGIModel):
        """Test."""

        year: int = Field(None)
        year1: int = Field(None)
        month1: int = Field(None)
        day1: int = Field(None)

    @iemapp(schema=MyModel)
    def application(environ, _start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "year=2022&month1=2&day1=3",
    }
    sr = mock.MagicMock()
    assert list(application(env, sr))[0].decode("ascii").find("Hello") > -1
    assert "_cgimodel_schema" in env


def test_iemapp_times_notime():
    """Test handling when no times provided."""

    class MyModel(CGIModel):
        """Test."""

        sts: AwareDatetime = Field(None)
        ets: AwareDatetime = Field(None)
        day1: int = Field(None)
        day2: int = Field(None)

    @iemapp(schema=MyModel)
    def application(environ, _start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "recent=yes",
    }
    sr = mock.MagicMock()
    assert list(application(env, sr))[0].decode("ascii").find("Hello") > -1


def test_iemapp_bracket_variable():
    """Test that a bracked variable is handled within pydantic schema."""

    class MyModel(CGIModel):
        """Test."""

        wfo: ListOrCSVType = Field(None)

    @iemapp(schema=MyModel)
    def application(environ, _start_response):
        """Test."""
        assert environ["wfo"] == ["DMX"]
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "wfo[]=DMX",
    }
    sr = mock.MagicMock()
    assert list(application(env, sr))[0].decode("ascii").find("Hello") > -1


def test_schema_with_parse_times():
    """Test that parse_times and schema can coexist."""

    class MyModel(CGIModel):
        """Test."""

        sts: Optional[datetime] = Field(None)
        day1: Optional[int] = Field(None)
        month1: Optional[int] = Field(None)
        year1: Optional[int] = Field(None)

    @iemapp(schema=MyModel, parse_times=True)
    def application(environ, _start_response):
        """Test."""
        assert environ["sts"] == datetime(
            2022, 2, 3, tzinfo=ZoneInfo("America/Chicago")
        )
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "year1=2022&month1=2&day1=3",
    }
    sr = mock.MagicMock()
    assert list(application(env, sr))[0].decode("ascii").find("Hello") > -1


def test_listorcsvtype():
    """Test that we can handle this."""

    class MyModel(CGIModel):
        """Test."""

        foo: ListOrCSVType = Field(...)
        foo2: ListOrCSVType = Field(...)
        foo3: ListOrCSVType = Field(...)
        valid: datetime = Field(None)
        foo4: str = Field(None)
        foo5: Optional[Union[None, datetime]] = Field(None)

    @iemapp(help="FINDME", schema=MyModel)
    def application(environ, _start_response):
        """Test."""
        assert environ["foo"] == ["1", "2"]
        assert environ["foo2"] == ["1", "2"]
        assert environ["foo3"] == ["1"]
        return [b"Content-type: text/plain\n\nHello!"]

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "foo=1&foo=2&foo2=1,2&foo3=1",
    }
    sr = mock.MagicMock()
    assert list(application(env, sr))[0].decode("ascii").find("Hello") > -1
    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "help",
    }
    assert list(application(env, sr))[0].decode("ascii").find("CGI") > -1
    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "foo=1&foo=2&foo2=1,2&foo3=1&valid=Foo",
    }
    assert (
        list(application(env, sr))[0].decode("ascii").find("datetime_from_d")
        > -1
    )

    env = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "foo=1&foo=2&foo2=1,2&foo3=1&foo4=<script>",
    }
    assert "akrherz" in list(application(env, sr))[0].decode("ascii")


def test_disable_parse_times():
    """Test that we can disable parsing times."""
    form = {
        "sts": "2023-09-11 1212",
    }
    environ = {}
    add_to_environ(environ, form, parse_times=False)
    assert environ["sts"] == form["sts"]


def test_add_telemetry_bad():
    """Test that an exception is caught."""
    assert not write_telemetry(
        TELEMETRY(
            timing=1,
            status_code=200,
            client_addr="",
            app="test",
            request_uri="",
            vhost="",
        ),
    )


def test_add_telemetry():
    """Test adding something to the queue."""
    assert write_telemetry(
        TELEMETRY(
            timing=1,
            status_code=200,
            client_addr=None,
            app="test",
            request_uri="",
            vhost="",
        ),
    )


def test_ensure_list():
    """Test that we get lists."""
    assert ensure_list({}, "a") == []
    assert ensure_list({"a": "b"}, "a") == ["b"]
    assert ensure_list({"a": ["b"]}, "a") == ["b"]
    assert ensure_list({"a": ["b,a"]}, "a", parse_commas=False) == ["b,a"]
    assert ensure_list({"a": "b,a"}, "a") == ["b", "a"]
    assert ensure_list({"a": ["c", "b,a"]}, "a") == ["c", "b", "a"]


def test_iemapp_help():
    """Test that help works."""

    @iemapp(help="FINDME")
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/?help")
    assert resp.status_code == 200
    assert "FINDME" in resp.text


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
    list(application(env, sr))
    assert env["sts"].year == 2021


def test_forgive_duplicate_tz():
    """Test the forgiveness of this combo."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/?tz=etc/utc&tz=etc/utc")
    assert resp.status_code == 200
    assert resp.text == "Hello!"


def test_duplicated_tz_in_form():
    """Test that this is handled."""

    @iemapp()
    def application(_environ, _start_response):
        """Test."""
        return [b"Content-type: text/plain\n\nHello!"]

    c = Client(application)
    resp = c.get("/?tz=etc/utc&tz=etc/UTC")
    assert "twice" in resp.text


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

    c = Client(application)
    resp = c.get("/")
    assert resp.status_code == 422


def test_newdatabase():
    """Test that the NewDatabaseConnectionError runs."""

    @iemapp()
    def application(_environ, _start_response):
        """Test."""
        raise NewDatabaseConnectionFailure()

    c = Client(application)
    resp = c.get("/")
    assert "akrherz" in resp.text


def test_nodatafound():
    """Test that the NoDataFound runs."""
    res = "Magic"

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise NoDataFound(res)

    c = Client(application)
    resp = c.get("/")
    assert resp.text == res


def test_iemapp_generator():
    """Test that we can wrap a generator."""

    @iemapp()
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        yield b"Hello!"

    c = Client(application)
    resp = c.get("/")
    assert resp.text == "Hello!"


def test_iemapp_decorator():
    """Try the API."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/")
    assert resp.text == "Hello!"


def test_typoed_tz():
    """Test that we handle when a tz gets commonly typoed."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/?tz=America/Chicage")
    assert resp.status_code == 200


def test_iemapp_raises_newdatabaseconnectionfailure():
    """Test catch a raised exception."""

    @iemapp()
    def application(_environ, _start_response):
        """Test."""
        get_dbconn("this will fail")
        return [b"Content-type: text/plain\n\nHello!"]

    c = Client(application)
    resp = c.get("/")
    assert resp.status_code == 503


def test_iemapp_catches_vanilla_exception():
    """Test catch a raised exception."""

    @iemapp()
    def application(environ, start_response):
        """Test."""
        raise Exception("This is a test")

    c = Client(application)
    resp = c.get("/")
    assert "akrherz" in resp.text


def test_iemapp_xss_javascript():
    """Test that javascript payload triggers XSS protection."""

    @iemapp()
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/?q=javascript:alert()")
    assert resp.status_code == 422
    assert "akrherz" in resp.text


def test_iemapp_xss_in_list():
    """Test that a list with javascript payload triggers XSS protection."""

    class MySchema(CGIModel):
        """Test."""

        q: ListOrCSVType = Field(...)

    @iemapp(schema=MySchema)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/?q=1&q=<script>alert('xss')</script>")
    assert resp.status_code == 422
    assert "akrherz" in resp.text
