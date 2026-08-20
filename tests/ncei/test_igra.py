"""Test IGRA ingest."""

import pytest

from pyiem.ncei.igra import process_ytd
from pyiem.util import get_test_filepath


def helper(filename: str):
    """Helper to process a sounding."""
    return list(process_ytd(get_test_filepath(filename)))


def test_260820_kabi_99hour():
    """Test that we can error with a bad header."""
    assert not helper("IGRA/KABI_99header.txt")


def test_simple():
    """Test simple things."""
    obj = helper("IGRA/OAX_25030812.txt")[0]
    assert obj.model.header.station == "USM00072558"


def test_krme_24070400_zero_rh():
    """Test a profile with 0 RH."""
    obj = helper("IGRA/KRME_24070400.txt")[0]
    assert obj.model.records[22].rh is None
    # Manually inserted a dwpc out of bounds, so the length should be one less
    assert len(obj.model.records) == 25


def test_cwpl_21041212():
    """Test missing release time."""
    obj = helper("IGRA/CWPL_21041212.txt")[0]
    assert obj.model.header.valid == obj.model.header.release_valid


def test_ytd():
    """Test parsing a ytd file (multiple records)."""
    res = helper("IGRA/OAX_ytd.txt")
    assert len(res) == 2


@pytest.mark.parametrize("database", ["raob"])
def test_sql(dbcursor):
    """Can we ingest the data to the database."""
    obj = helper("IGRA/OAX_25030812.txt")[0]
    obj.sql(dbcursor)
