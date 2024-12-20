"""Test the gridnav module."""

import pytest

from pyiem.models.gridnav import CartesianGridNavigation


@pytest.fixture
def cgn() -> CartesianGridNavigation:
    """Return a basic CartesianGridNavigation."""
    return CartesianGridNavigation(
        left_edge=0,
        bottom_edge=0,
        dx=1,
        dy=1,
        nx=10,
        ny=10,
    )


def test_api(cgn):
    """Test basic things."""
    assert cgn.bottom == 0.5
    assert len(cgn.x_points) == 10
    assert len(cgn.y_points) == 10
    assert len(cgn.x_edges) == 11
    assert len(cgn.y_edges) == 11
    assert cgn.right == cgn.x_points[-1]


def test_find_ij(cgn):
    """See if we can get the right cell."""
    i, j = cgn.find_ij(0.5, 0.5)
    assert i == 0
    assert j == 0
    i, j = cgn.find_ij(0.5, 10.5)
    assert i is None
    assert j is None
