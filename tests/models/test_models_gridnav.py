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


def test_non_even_spacing():
    """Test that this errors."""
    with pytest.raises(ValueError):
        CartesianGridNavigation(
            left_edge=0,
            bottom_edge=0,
            top_edge=10,
            right_edge=10,
            dx=2.2,
            dy=0.7,
        )


def test_computing_dxdy():
    """Test that we can get a dx and dy."""
    _cgn = CartesianGridNavigation(
        left_edge=0,
        bottom_edge=0,
        nx=10,
        ny=10,
        right_edge=10,
        top_edge=10,
    )
    assert _cgn.dx == 1
    assert _cgn.dy == 1


def test_computing_nxny():
    """Test that ny and ny can be computed."""
    _cgn = CartesianGridNavigation(
        left_edge=0,
        bottom_edge=0,
        dx=1,
        dy=1,
        right_edge=10,
        top_edge=10,
    )
    assert _cgn.nx == 10
    assert _cgn.ny == 10


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
