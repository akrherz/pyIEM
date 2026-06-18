"""Tests for web/error.py."""

import random

import pytest
from werkzeug.test import Client

from pyiem.web.error import application


@pytest.fixture
def random_ipv4():
    """GEnerate a quasi random IP."""
    # First octet can't trip our ISU self-network check, sigh
    return (
        f"100.{random.randint(1, 255)}."
        f"{random.randint(1, 255)}.{random.randint(1, 255)}"
    )


def test_error404(random_ipv4: str):
    """Test basic handling of errors coming from the IEM webfarm."""

    eo = {"REMOTE_ADDR": random_ipv4, "HTTP_HOST": "mesonet.agron.iastate.edu"}
    c = Client(application)
    resp = c.get("/?q=1", environ_overrides=eo)
    assert resp.status_code == 404


def test_archivere_handler(random_ipv4: str):
    """Test the archive handler."""
    eo = {"REMOTE_ADDR": random_ipv4, "HTTP_HOST": "mesonet.agron.iastate.edu"}
    c = Client(application)
    resp = c.get(
        "/archive/data/2020/01/01/foo_20200101_0000", environ_overrides=eo
    )
    assert resp.status_code == 404


def test_archivere_invalid_timestamp(random_ipv4: str):
    """Test the archive handler."""
    eo = {"REMOTE_ADDR": random_ipv4, "HTTP_HOST": "mesonet.agron.iastate.edu"}
    c = Client(application)
    resp = c.get(
        "/archive/data/2020/01/01/foo_20200231_000000", environ_overrides=eo
    )
    assert resp.status_code == 404


def test_archivere_future_timestamp(random_ipv4: str):
    """Test the archive handler."""
    eo = {"REMOTE_ADDR": random_ipv4, "HTTP_HOST": "mesonet.agron.iastate.edu"}
    c = Client(application)
    resp = c.get(
        "/archive/data/2020/01/01/foo_20990101_000000", environ_overrides=eo
    )
    assert resp.status_code == 422


def test_wms_handler(random_ipv4: str):
    """Test the WMS handler."""
    eo = {"REMOTE_ADDR": random_ipv4, "HTTP_HOST": "mesonet.agron.iastate.edu"}
    c = Client(application)
    resp = c.get("/?q=1&service=WMS", environ_overrides=eo)
    assert resp.status_code == 400
    assert "/ogc" in resp.text


def test_log_request_error(random_ipv4: str):
    """Test a null byte causing log request to fail."""
    eo = {
        "REMOTE_ADDR": random_ipv4,
        "HTTP_REFERER": "http://example.com/\x00",
        "HTTP_HOST": "mesonet.agron.iastate.edu",
    }
    c = Client(application)
    resp = c.get("/?q=1", environ_overrides=eo)
    assert resp.status_code == 404


def test_405_handler(random_ipv4: str):
    """Test the 405 handler."""
    eo = {
        "REMOTE_ADDR": random_ipv4,
        "REDIRECT_STATUS": 405,
        "HTTP_HOST": "mesonet.agron.iastate.edu",
    }
    c = Client(application)
    resp = c.post("/?q=1", environ_overrides=eo)
    assert resp.status_code == 301


def test_404_non_iemhost(random_ipv4: str):
    """Test the 404 handler for non IEM hosts."""
    eo = {"REMOTE_ADDR": random_ipv4, "HTTP_HOST": "example.com"}
    c = Client(application)
    resp = c.get("/?q=1", environ_overrides=eo)
    assert resp.status_code == 404
