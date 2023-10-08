"""Test the version module."""

import mock
from pyiem._version import get_version


def test_version():
    """Test the version."""
    assert get_version()
    # mock the setuptools_scm import to fail
    with mock.patch("setuptools_scm.get_version") as gv:
        gv.side_effect = ImportError
        assert get_version()
