"""Testing FFG parsing."""

import pytest
from pyiem.nws.products.ffg import parser as ffgparser
from pyiem.util import get_test_file


@pytest.mark.parametrize("database", ["postgis"])
def test_ffg(dbcursor):
    """FFG"""
    prod = ffgparser(get_test_file("FFGJAN.txt"))
    prod.sql(dbcursor)
    assert len(prod.data.index) == 53


@pytest.mark.parametrize("database", ["postgis"])
def test_ffg2(dbcursor):
    """FFGKY"""
    prod = ffgparser(get_test_file("FFGKY.txt"))
    prod.sql(dbcursor)
    assert len(prod.data.index) == 113


@pytest.mark.parametrize("database", ["postgis"])
def test_ffgama(dbcursor):
    """FFGAMA"""
    prod = ffgparser(get_test_file("FFGAMA.txt"))
    prod.sql(dbcursor)
    assert len(prod.data.index) == 23
