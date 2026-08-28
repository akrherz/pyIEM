"""Test iemapp specific things from webutil."""

import random
from datetime import datetime
from typing import Annotated, Optional, Union
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from pydantic import AwareDatetime, Field, field_validator
from werkzeug.test import Client

from pyiem.database import get_dbconn
from pyiem.exceptions import (
    IncompleteWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
from pyiem.webutil import CGIModel, ListOrCSVType, iemapp, ip_is_throttled


@pytest.fixture
def random_ipv4():
    """GEnerate a quasi random IP."""
    # First octet can't trip our ISU self-network check, sigh
    return (
        f"100.{random.randint(1, 255)}."
        f"{random.randint(1, 255)}.{random.randint(1, 255)}"
    )


def test_ip_is_throttled_with_memcache_exception(random_ipv4: str):
    """Test that a memcache exception is properly handled."""

    class DummyMemcacheClient:
        """Simple in-memory memcache stand-in for deterministic testing."""

        def __init__(self, _server):
            """."""
            self.cache = {}

        def add(self, _key, _value, expire=None, noreply=False):
            return self.cache["WillRaiseException"]

        def close(self):
            """."""

    with mock.patch("pyiem.webutil.Client", DummyMemcacheClient):
        assert not ip_is_throttled({"REMOTE_ADDR": random_ipv4}, 1)


def test_gh1248_default_tz():
    """Test that default_tz is used for sts and ets generation."""

    class Schema(CGIModel):
        sts: Annotated[datetime, Field(description="Start Time")] = None
        ets: Annotated[datetime, Field(description="End Time")] = None

    @iemapp(help="FINDME", schema=Schema, default_tz="America/New_York")
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return (
            "OK"
            if (
                environ["sts"].tzinfo is not None
                and environ["ets"].tzinfo is not None
                and environ["sts"].tzinfo.key == "America/New_York"
                and environ["ets"].tzinfo.key == "America/New_York"
            )
            else "FAIL"
        )

    c = Client(application)
    resp = c.get("/?sts=2022-01-01T00:00&ets=2022-01-02T00:00")
    assert resp.status_code == 200
    assert resp.text == "OK"


def test_gh1248_default_tz_not_set():
    """Test for naive sts when default_tz is not set.."""

    class Schema(CGIModel):
        sts: Annotated[datetime, Field(description="Start Time")] = None

    @iemapp(help="FINDME", schema=Schema)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return "OK" if environ["sts"].tzinfo is None else "FAIL"

    c = Client(application)
    resp = c.get("/?sts=2022-01-01T00:00")
    assert resp.status_code == 200
    assert resp.text == "OK"


def test_gh1248_default_tz_invalid_tz_provided():
    """Test that this situation errors 422."""

    class Schema(CGIModel):
        sts: Annotated[datetime, Field(description="Start Time")] = None
        tz: Annotated[str | None, Field(description="Timezone")] = None

    @iemapp(help="FINDME", schema=Schema, default_tz="America/New_York")
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return "OK"

    c = Client(application)
    resp = c.get("/?sts=2022-01-01T00:00&tz=America/")
    assert resp.status_code == 422


def test_gh1248_default_tz_invalid_tz_optional():
    """Test that this situation errors 422."""

    class Schema(CGIModel):
        sts: Annotated[datetime, Field(description="Start Time")] = None
        tz: Annotated[str | None, Field(description="Timezone")] = None

    @iemapp(help="FINDME", schema=Schema, default_tz="America/New_York")
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return (
            "OK" if environ["sts"].tzinfo.key == "America/New_York" else "FAIL"
        )

    c = Client(application)
    resp = c.get("/?sts=2022-01-01T00:00")
    assert resp.status_code == 200
    assert resp.text == "OK"


def test_iemapp_help_with_linereturns():
    """Test that we properly convert descriptions with newlines."""

    class Schema(CGIModel):
        bah: Annotated[
            str,
            Field(
                description="""
    For near realtime requests, the number of seconds to go back in
    time.  The timestamp query is the time of the LSR report, not
    the time it was disseminated by the NWS. Must be less than
    1,000,000 seconds."""
            ),
        ]
        foo: Annotated[str, Field(description="Uninteresting")]

    @iemapp(help="FINDME", schema=Schema)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    resp = c.get("/?help")
    assert resp.status_code == 200
    assert "list-table::" not in resp.text


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


def test_iemapp_help_logs_docutils_warning():
    """Test that malformed RST help text triggers warning logging."""

    @iemapp(help="Heading\n----")
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Hello!"]

    c = Client(application)
    with mock.patch("pyiem.webutil.LOG.warning") as mock_warning:
        resp = c.get("/?help")
    assert resp.status_code == 200
    assert mock_warning.called


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

    class Schema(CGIModel):
        tz: Annotated[str, Field(description="tz")]

    @iemapp(schema=Schema)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return environ["tz"]

    c = Client(application)
    resp = c.get("/?tz=central")
    assert resp.status_code == 200
    assert resp.text == "America/Chicago"


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


def test_options(random_ipv4: str):
    """Test that OPTIONS requests are automagically handled."""

    @iemapp()
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return f"{random.random()}"

    eo = {"REMOTE_ADDR": random_ipv4}
    c = Client(application)
    resp = c.options("/?q=-1", environ_overrides=eo)
    assert resp.status_code == 204
    assert not resp.text
    assert resp.headers["Allow"] == "GET, OPTIONS"


def test_ip_throttled_callable(random_ipv4: str):
    """Test that the ip throttle is callable."""

    class Schema(CGIModel):
        """Test."""

        q: Annotated[int, Field(description="A")] = 0

    @iemapp(
        schema=Schema,
        ip_throttle_secs=lambda x: 0 if x["q"] < 0 else 10,
    )
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return f"{random.random()}"

    eo = {"REMOTE_ADDR": random_ipv4}
    c = Client(application)
    resp = c.get("/?q=-1", environ_overrides=eo)
    assert resp.status_code == 200
    resp = c.get("/?q=-1", environ_overrides=eo)
    assert resp.status_code == 200


def test_ip_throttled(random_ipv4: str):
    """Test how our throttle behaves."""

    @iemapp(ip_throttle_secs=10)
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return f"{random.random()}"

    eo = {"REMOTE_ADDR": random_ipv4}
    c = Client(application)
    resp = c.get("/?q=1", environ_overrides=eo)
    assert resp.status_code == 200, resp.text
    resp = c.get("/?q=1", environ_overrides=eo)
    assert resp.status_code == 429, resp.text


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


def test_empty_string():
    """Test that empty strings are not passed through..."""

    class MyModel(CGIModel):
        bogus: Annotated[float | None, Field("Float")] = None

    @iemapp(schema=MyModel)
    def application(environ, start_response):
        """Test."""
        assert environ["bogus"] is None
        start_response("200 OK", [("Content-type", "text/plain")])
        return environ.get("unused", "OK")

    c = Client(application)
    resp = c.get("/?bogus=")
    assert resp.status_code == 200
    assert resp.text == "OK"


def test_gh1174_self():
    """Test what happens with CGI self= is processed."""

    class MyModel(CGIModel):
        bogus: Annotated[str, Field(description="bah")] = "bah"

    @iemapp(schema=MyModel)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return environ.get("unused", "OK")

    c = Client(application)
    resp = c.get("/?self=1&unused=1")
    assert resp.status_code == 200
    assert resp.text == "OK"


def test_iemweb_datetime_type():
    """Test the handling of a datetime schema field."""

    class MyModel(CGIModel):
        """Test."""

        state: str = Field(...)
        dt: datetime = Field(default=None)

        # This is important to get the dt type to datetime prior to going to
        # XSS
        @field_validator("dt", mode="before")
        @classmethod
        def parse_valid(cls, value, _info):
            """Ensure we have a valid time."""
            fmt = "%Y%m%d%H%M"
            if value.find("T") > 0 and len(value) >= 16:
                fmt = "%Y-%m-%dT%H:%M"
                value = value[:16]
            return datetime.strptime(value, fmt)

    @iemapp(schema=MyModel)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        is_dt = isinstance(environ["dt"], datetime)
        return f"{environ['dt'].year if is_dt else 'bad'}"

    c = Client(application)
    resp = c.get("/?state=IA&dt=2022-01-01T00:00:00Z")
    assert resp.status_code == 200
    assert resp.text == "2022"


def test_iemweb_int_type():
    """Test that we don't allow a list in the parsed form."""

    class MyModel(CGIModel):
        """Test."""

        f: int = Field(...)

    @iemapp(schema=MyModel)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return f"{environ['f'] if isinstance(environ['f'], int) else 'bad'}"

    c = Client(application)
    resp = c.get("/?f=1")
    assert resp.status_code == 200
    assert resp.text == "1"


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


def test_iemapp_telemetry_skipped_on_memcache_hit():
    """Test that telemetry is not written when response is memcache-backed."""

    cache = {}

    class DummyMemcacheClient:
        """Simple in-memory memcache stand-in for deterministic testing."""

        def __init__(self, _server):
            """."""

        @staticmethod
        def get(key):
            """."""
            return cache.get(key)

        @staticmethod
        def set(key, value, expire=None):
            """."""
            cache[key] = value

        @classmethod
        def close(cls):
            """."""

    @iemapp(memcachekey="iem")
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return b"Hello!"

    with (
        mock.patch("pyiem.webutil.Client", DummyMemcacheClient),
        mock.patch("pyiem.webutil.write_telemetry") as write_mock,
    ):
        c = Client(application)
        assert c.get("/").status_code == 200
        assert c.get("/").status_code == 200
    assert write_mock.call_count == 1


def test_iemapp_telemetry_uses_captured_start_response_status():
    """Test telemetry logs status emitted by downstream start_response."""

    @iemapp()
    def application(_environ, start_response):
        """Test."""
        start_response("404 Not Found", [("Content-type", "text/plain")])
        return b"missing"

    with mock.patch("pyiem.webutil.write_telemetry") as write_mock:
        c = Client(application)
        resp = c.get("/")
    assert resp.status_code == 404
    assert write_mock.call_count == 1
    assert write_mock.call_args[0][0].status_code == 404


def test_iemapp_generator_exception_after_start_response(random_ipv4: str):
    """Test post-start generator exceptions are logged without restart."""

    start_response_calls = []

    @iemapp()
    def application(_environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        yield b"first"
        raise RuntimeError("boom")

    environ = {
        "wsgi.input": mock.MagicMock(),
        "QUERY_STRING": "",
        "REQUEST_URI": "/",
        "REMOTE_ADDR": random_ipv4,
    }

    def sr(status, headers):
        start_response_calls.append((status, headers))

    with mock.patch("pyiem.webutil.LOG.exception") as mock_exception:
        res = list(application(environ, sr))
    assert res == [b"first"]
    assert len(start_response_calls) == 1
    assert start_response_calls[0][0] == "200 OK"
    assert mock_exception.call_count == 1


def test_sts_ets_are_set():
    """Test that we cross set things properly."""

    class MyModel(CGIModel):
        """Test."""

        sts: datetime = Field(None)
        ets: datetime = Field(None)
        year1: int = Field(None)
        month1: int = Field(None)
        day1: int = Field(None)
        year2: int = Field(None)
        month2: int = Field(None)
        day2: int = Field(None)

    @iemapp(schema=MyModel)
    def application(environ, start_response):
        """Test."""
        assert environ["sts"] == environ["_cgimodel_schema"].sts
        assert environ["ets"] == environ["_cgimodel_schema"].ets
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Content-type: text/plain\n\nHello!"]

    client = Client(application)
    resp = client.get(
        "/?year1=2022&month1=2&day1=3&year2=2023&month2=1&day2=1"
    )
    assert resp.status_code == 200
    assert resp.text.find("Hello") > -1


def test_iemapp_year_year1():
    """Test that we can handle a legacy situation with DCP app."""

    class MyModel(CGIModel):
        """Test."""

        year: int = Field(None)
        year1: int = Field(None)
        month1: int = Field(None)
        day1: int = Field(None)

    @iemapp(schema=MyModel)
    def application(environ, start_response):
        """Test."""
        start_response("200 OK", [("Content-type", "text/plain")])
        return [b"Content-type: text/plain\n\nHello!"]

    client = Client(application)
    resp = client.get("/?year=2022&month1=2&day1=3")
    assert resp.status_code == 200
    assert resp.text.find("Hello") > -1


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
