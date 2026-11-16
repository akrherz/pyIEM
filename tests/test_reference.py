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
    seen = {}
    dups = []
    with open(fn) as fh:
        for line in fh:
            if line and not line.startswith("#"):
                tokens = line.strip().split()
                key = tokens[0]
                if key in seen:
                    dups.append(key)
                seen[key] = True
    assert not dups, f"Found duplicate keys: {dups}"


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
