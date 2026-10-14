"""Test pyiem.plot.textcollider."""

from pyiem.plot.textcollider import TextCollider


def test_empty():
    """An empty collider never collides."""
    tc = TextCollider()
    assert len(tc) == 0
    assert not tc.collides((0, 0, 10, 10), 1)


def test_overlap_and_disjoint():
    """Overlapping boxes collide, disjoint ones do not."""
    tc = TextCollider()
    assert tc.try_claim((0, 0, 10, 10), 1)
    assert not tc.try_claim((5, 5, 15, 15), 1)
    assert tc.try_claim((20, 20, 30, 30), 1)
    assert len(tc) == 2


def test_touching_edges_do_not_collide():
    """Boxes that merely share an edge do not overlap."""
    tc = TextCollider()
    tc.claim((0, 0, 10, 10), 1)
    assert not tc.collides((10, 0, 20, 10), 1)
    assert not tc.collides((0, 10, 10, 20), 1)


def test_padding():
    """Padding on either side widens the required gap."""
    tc = TextCollider()
    tc.claim((0, 0, 10, 10), 1)
    assert not tc.collides((15, 0, 25, 10), 1)
    # Gap of 5 < 2 * 3
    assert tc.collides((15, 0, 25, 10), 1, xpad=3)
    # Padding is independent per axis
    assert not tc.collides((0, 15, 10, 25), 1, xpad=3)
    assert tc.collides((0, 15, 10, 25), 1, ypad=3)


def test_zorder_priority():
    """Only boxes of equal or higher zorder block a candidate."""
    tc = TextCollider()
    tc.claim((0, 0, 10, 10), 5)
    assert tc.collides((0, 0, 10, 10), 5)
    assert tc.collides((0, 0, 10, 10), 4)
    assert not tc.collides((0, 0, 10, 10), 6)


def test_failed_claim_is_not_recorded():
    """A rejected claim must not occupy space."""
    tc = TextCollider()
    tc.claim((0, 0, 10, 10), 1)
    assert not tc.try_claim((5, 5, 15, 15), 1)
    assert len(tc) == 1
    assert tc.try_claim((11, 11, 20, 20), 1)
