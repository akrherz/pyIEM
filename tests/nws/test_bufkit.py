"""Test BUFKIT"""
# stdlib
from io import StringIO

# third party
import pytest

# Local
from pyiem.util import get_test_file
from pyiem.nws.bufkit import read_bufkit


@pytest.mark.parametrize(
    "model", ["gfs3", "nam", "gfsm", "namm", "hrrr", "rap"]
)
def test_reader(model):
    """Test reading a GFS file."""
    sndf, stndf = read_bufkit(
        get_test_file(f"BUFKIT/{model}_kdsm.buf", fnonly=True)
    )
    assert sndf["STIM"].max() == stndf.index.values[-1]


def test_values():
    """Test that we get values we expect."""
    sndf, stndf = read_bufkit(
        get_test_file("BUFKIT/namm_kdsm.buf", fnonly=True)
    )
    row = sndf[(sndf["STIM"] == 0) & (sndf["PRES"] == 7.60)]
    assert abs(float(row["HGHT"]) - 33326.51) < 0.01
    row = stndf.loc[84]
    assert abs(float(row["TD2M"]) - 15.79) < 0.01


def test_stringio():
    """Can we read a stringIO object."""
    fn = get_test_file("BUFKIT/namm_kdsm.buf", fnonly=True)
    sio = StringIO()
    sio.write(open(fn).read())
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
