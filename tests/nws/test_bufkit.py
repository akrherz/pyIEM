"""Test BUFKIT"""

# stdlib
from io import StringIO

# third party
import pytest

from pyiem.nws.bufkit import read_bufkit

# Local
from pyiem.util import get_test_filepath


@pytest.mark.parametrize(
    "model", ["gfs3", "nam", "gfsm", "namm", "hrrr", "rap"]
)
def test_reader(model):
    """Test reading a GFS file."""
    fp = get_test_filepath(f"BUFKIT/{model}_kdsm.buf")
    sndf, stndf = read_bufkit(fp)
    assert sndf["STIM"].max() == stndf.index.values[-1]


def test_251112_nam4km_klga():
    """Test a failure found parsing a BUFKIT file from 2023."""
    fp = get_test_filepath("BUFKIT/nam4km_klga.buf")
    sndf, stndf = read_bufkit(fp)
    assert not sndf.empty
    assert not stndf.empty


def test_251112_hrrr_klax():
    """Test a failure found parsing a BUFKIT file from 2020."""
    fp = get_test_filepath("BUFKIT/hrrr_klax.buf")
    sndf, stndf = read_bufkit(fp)
    assert not sndf.empty
    assert not stndf.empty


def test_values():
    """Test that we get values we expect."""
    fp = get_test_filepath("BUFKIT/namm_kdsm.buf")
    sndf, stndf = read_bufkit(fp)
    row = sndf[(sndf["STIM"] == 0) & (sndf["PRES"] == 7.60)].iloc[0]
    assert abs(float(row["HGHT"]) - 33326.51) < 0.01
    row = stndf.loc[84]
    assert abs(float(row["TD2M"]) - 15.79) < 0.01


def test_stringio():
    """Can we read a stringIO object."""
    fp = get_test_filepath("BUFKIT/namm_kdsm.buf")
    sio = StringIO()
    with open(fp, encoding="utf-8") as fh:
        sio.write(fh.read())
    sndf, stndf = read_bufkit(sio)
    assert sndf is not None
    assert stndf is not None


def test_invalid_args():
    """Test passing garbage."""
    with pytest.raises(ValueError):
        read_bufkit(None)
    sio = StringIO()
    sio.write("ZZZZZZZZZZZZZZ")
    with pytest.raises(ValueError):
        read_bufkit(sio)
