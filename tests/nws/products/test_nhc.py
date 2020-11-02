"""Test NHC."""

from pyiem.nws.products.nhc import parser as nhcparser
from pyiem.util import get_test_file


def test_issue317_nowarning():
    """Test that no warning is emitted for a tropical product from TJSJ."""
    prod = nhcparser(get_test_file("tropical/TCPSP4.txt"))
    prod.get_jabbers("http://localhost", "http://localhost")
    assert not prod.warnings


def test_170618_potential():
    """New TCP type"""
    prod = nhcparser(get_test_file("TCPAT2.txt"))
    assert not prod.warnings
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "National Hurricane Center issues ADVISORY 2 "
        "for POTENTIAL TROPICAL CYCLONE TWO "
        "http://localhost?pid=201706190300-KNHC-WTNT32-TCPAT2"
    )
    assert j[0][0] == ans


def test_160905_correction():
    """See that a product correction does not trip us"""
    prod = nhcparser(get_test_file("TCPAT4.txt"))
    assert not prod.warnings
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "National Hurricane Center issues ADVISORY 28A "
        "for POST-TROPICAL CYCLONE HERMINE INTERMEDIATE "
        "http://localhost?pid=201609041200-KNHC-WTNT34-TCPAT4"
    )
    assert j[0][0] == ans
