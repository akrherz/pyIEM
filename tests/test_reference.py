"""Is our reference hackery usable."""

# Local
from pyiem import reference


def test_states():
    """Test that we have the same number of states"""
    assert len(reference.state_names) == len(reference.state_bounds)
    _ = [reference.state_bounds[x] for x in reference.state_names]


def test_reference():
    """Can we import everything from our API."""
    for name in reference._onthefly_dict:
        res = getattr(reference, name, None)
        # is a dictionary
        assert isinstance(res, dict)
        # has keys
        assert res.keys()
