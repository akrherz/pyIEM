"""Test pyiem module level stuff."""

import importlib
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import pyiem


def test_version_not_installed():
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        importlib.reload(pyiem)
        assert pyiem.__version__ == "dev"


def test_version_dev():
    with patch("os.path.dirname", return_value="/path/to/source"):
        importlib.reload(pyiem)
        assert pyiem.__version__.endswith("-dev")


def test_version():
    """Test that version works."""
    assert pyiem.__version__ is not None
