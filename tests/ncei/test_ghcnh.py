"""Test GHCNh parsing, joy."""

from pyiem.ncei.ghcnh import process_file
from pyiem.reference import TRACE_VALUE, VARIABLE_WIND_DIRECTION
from pyiem.util import get_test_filepath


def test_variable_wind():
    """Test when VRB is provided as the value, which I think is a bug."""
    fn = get_test_filepath("GHCNh/GHCNh_USW00026442_por.psv")
    res = list(process_file(fn))
    assert res[0]["drct"] == VARIABLE_WIND_DIRECTION


def test_kbtm():
    """Test edge cases found with this example file."""
    fn = get_test_filepath("GHCNh/GHCNh_USW00024135_por.psv")
    res = list(process_file(fn))
    assert res[0]["raw"].find("SNB01E15B26") > 0
    assert abs(res[1]["phour"] - TRACE_VALUE) < 0.0001
    assert abs(res[3]["phour"] - 0.01) < 0.001
    assert res[4]["raw"].find(" KT ") == -1


def test_kokc():
    """Test edge cases found with this example file."""
    fn = get_test_filepath("GHCNh/GHCNh_USW00013967_por.psv")
    res = list(process_file(fn))
    assert abs(res[0]["gust"] - 35) < 0.0001
    assert abs(res[1]["p24i"] - 0.07) < 0.0001
    assert res[2]["tmpf"] is None
    assert abs(res[3]["p06i"] - TRACE_VALUE) < 0.0001


def test_ntat():
    """Test example with bad VSBY."""
    fn = get_test_filepath("GHCNh/GHCNh_FPI0000NTAT_por.psv")
    res = list(process_file(fn))
    assert res[0]["vsby"] is None
