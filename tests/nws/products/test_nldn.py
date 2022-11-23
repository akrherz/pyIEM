"""Test NLDN."""

import pytest
from pyiem.nws.products.nldn import parser
from pyiem.util import get_test_filepath


def test_1_basic():
    """CLIBNA is a new diction"""
    fp = get_test_filepath("NLDN/example.bin")
    with open(fp, "rb") as fh:
        np = parser(fh)
    assert len(np.df.index) == 50


@pytest.mark.parametrize("database", ["nldn"])
def test_sql(dbcursor):
    """Test that we can insert data."""
    fp = get_test_filepath("NLDN/example.bin")
    with open(fp, "rb") as fh:
        np = parser(fh)
    np.sql(dbcursor)
