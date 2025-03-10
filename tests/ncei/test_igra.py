"""Test IGRA ingest."""

import pytest

from pyiem.ncei.igra import process_sounding, process_ytd
from pyiem.util import get_test_file, get_test_filepath


def test_simple():
    """Test simple things."""
    obj = process_sounding(get_test_file("IGRA/OAX_25030812.txt"))
    assert obj.model.header.station == "USM00072558"


def test_cwpl_21041212():
    """Test missing release time."""
    obj = process_sounding(get_test_file("IGRA/CWPL_21041212.txt"))
    assert obj.model.header.valid == obj.model.header.release_valid


def test_ytd():
    """Test parsing a ytd file (multiple records)."""
    res = list(process_ytd(get_test_filepath("IGRA/OAX_ytd.txt")))
    assert len(res) == 2


@pytest.mark.parametrize("database", ["raob"])
def test_sql(dbcursor):
    """Can we ingest the data to the database."""
    obj = process_sounding(get_test_file("IGRA/OAX_25030812.txt"))
    obj.sql(dbcursor)
