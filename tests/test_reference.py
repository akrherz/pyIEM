"""Is our reference hackery usable."""

from pathlib import Path

from pyiem import reference


def test_igra2icao_is_unique():
    """Test that we have no dups in the lookup."""
    fn = (
        Path(__file__).parent.parent
        / "src"
        / "pyiem"
        / "data"
        / "reference"
        / "igra2icao.txt"
    )
    keys_seen = {}
    values_seen = {}
    with open(fn) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split()
                if key in keys_seen:
                    raise AssertionError(f"Duplicate key found: {key}")
                if value in values_seen:
                    raise AssertionError(f"Duplicate value found: {value}")
                keys_seen[key] = True
                values_seen[value] = True


def test_ugc_state_names_in_state_names():
    """Test that ugc_state_names is a superset of state_names."""
    assert all(x in reference.ugc_state_names for x in reference.state_names)


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
