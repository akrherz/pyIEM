"""test NWSLI."""

from pyiem.nws.nwsli import NWSLI


def test_simple():
    """See if we can generate a proper string from a UGCS"""
    nwsli = NWSLI("AMWI4", "Iowa All", ["DMX"], -99, 44)
    assert nwsli.id == "AMWI4"

    assert nwsli.get_name() == "Iowa All"
