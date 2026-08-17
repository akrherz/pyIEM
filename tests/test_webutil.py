"""Tests for webutil."""

import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import mock
import pytest
from pydantic import Field, ValidationError

from pyiem.exceptions import (
    BadWebRequest,
    IncompleteWebRequest,
)
from pyiem.reference import ISO8601
from pyiem.webutil import (
    RSYSLOG_SIDEDOOR_SOCKET,
    TELEMETRY,
    CGIModel,
    ListOrCSVType,
    _is_xss_payload,
    add_to_environ,
    ensure_list,
    ip_is_throttled,
    write_telemetry,
)


@pytest.fixture
def random_ipv4():
    """GEnerate a quasi random IP."""
    # First octet can't trip our ISU self-network check, sigh
    return (
        f"100.{random.randint(1, 255)}."
        f"{random.randint(1, 255)}.{random.randint(1, 255)}"
    )


def test_telemetry_null_byte_request_uri():
    """Ensure null bytes are not allowed in the URL."""
    with pytest.raises(ValidationError, match="request_uri"):
        TELEMETRY(
            timing=1,
            status_code=200,
            client_addr="127.0.0.1",
            app="test",
            request_uri="/hi\x00",
            vhost="",
            valid=datetime.now().strftime(ISO8601),
        )


def test_telemetry_null_byte_app():
    """Ensure null bytes are not allowed in the URL."""
    with pytest.raises(ValidationError, match="app"):
        TELEMETRY(
            timing=1,
            status_code=200,
            client_addr="127.0.0.1",
            app="test\x00",
            request_uri="/hi",
            vhost="",
            valid=datetime.now().strftime(ISO8601),
        )


def test_telemetry_bad_ip():
    """Test that we do not allow a bad IP within TELEMETRY."""
    with pytest.raises(ValidationError, match="client_addr"):
        TELEMETRY(
            timing=1,
            status_code=200,
            client_addr="not_an_ip",
            app="test",
            request_uri="",
            vhost="",
            valid=datetime.now().strftime(ISO8601),
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


def test_ip_is_throttled_with_memcache_exception(random_ipv4: str):
    """Test that a memcache exception is properly handled."""

    class DummyMemcacheClient:
        """Simple in-memory memcache stand-in for deterministic testing."""

        def __init__(self, _server):
            """."""

        def add(self, _key, _value, expire=None, noreply=False):
            raise Exception("Memcache add failed")

        def close(self):
            """."""

    with mock.patch("pyiem.webutil.Client", DummyMemcacheClient):
        assert not ip_is_throttled({"REMOTE_ADDR": random_ipv4}, 1)


def test_listorcsvtype_provided_list_with_csv():
    """Test that we flatten this situation."""

    class MyModel(CGIModel):
        """Test."""

        wfo: ListOrCSVType = Field(None)

    res = MyModel(wfo=["BGM,DMX"])
    assert res.wfo == ["BGM", "DMX"]


def test_listorcsvtype_provided_list_with_csv_and_other():
    """Test that we flatten this situation."""

    class MyModel(CGIModel):
        """Test."""

        wfo: ListOrCSVType = Field(None)

    res = MyModel(wfo=["BGM,DMX", "DVN"])
    assert res.wfo == ["BGM", "DMX", "DVN"]


def test_disable_parse_times():
    """Test that we can disable parsing times."""
    form = {
        "sts": "2023-09-11 1212",
    }
    environ = {}
    add_to_environ(environ, form, parse_times=False)
    assert environ["sts"] == form["sts"]


def test_add_telemetry():
    """Test adding something to the rsyslog sidedoor socket."""
    now = datetime.now(timezone.utc)
    data = TELEMETRY(
        timing=1,
        status_code=200,
        client_addr=None,
        app="test",
        request_uri="",
        vhost="",
        valid=now.strftime(ISO8601),
    )
    socket_mock = mock.MagicMock()
    cm_mock = mock.MagicMock()
    cm_mock.__enter__.return_value = socket_mock
    cm_mock.__exit__.return_value = False
    with mock.patch("pyiem.webutil.socket.socket", return_value=cm_mock):
        assert write_telemetry(data)

    socket_mock.setblocking.assert_called_once_with(False)
    socket_mock.sendto.assert_called_once_with(
        b"<141>Telemetry "
        + (
            b'{"timing":1.0,"status_code":200,"client_addr":null,'
            b'"app":"test","request_uri":"","vhost":"","valid":"'
            + now.strftime(ISO8601).encode("utf-8")
            + b'"}'
        ),
        RSYSLOG_SIDEDOOR_SOCKET,
    )


def test_add_telemetry_failure_is_swallowed():
    """Test telemetry failures stay contained inside write_telemetry."""
    with mock.patch("pyiem.webutil.socket.socket", side_effect=OSError()):
        assert not write_telemetry(
            TELEMETRY(
                timing=1,
                status_code=200,
                client_addr=None,
                app="test",
                request_uri="",
                vhost="",
                valid=datetime.now().strftime(ISO8601),
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
