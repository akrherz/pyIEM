"""Test DEP"""
import os
import datetime

from pyiem import dep


def get_path(name):
    """helper"""
    basedir = os.path.dirname(__file__)
    return "%s/../data/wepp/%s" % (basedir, name)


def test_ramps():
    """Ramps should be of length 11"""
    for q in dep.RAMPS:
        for val in dep.RAMPS[q]:
            assert len(val) == 9


def test_scenarios():
    """Can we load scenarios?"""
    df = dep.load_scenarios()
    assert not df.empty
    assert 0 in df.index


def test_cli_fname():
    """Do we get the right climate file names?"""
    res = dep.get_cli_fname(-95.5, 42.5, 0)
    assert res == "/i/0/cli/095x042/095.50x042.50.cli"
    res = dep.get_cli_fname(-97.9999, 42.0, 0)
    assert res == "/i/0/cli/098x042/098.00x042.00.cli"


def test_crop():
    """Read a crop file."""
    df = dep.read_crop(get_path("crop.txt"))
    assert len(df.index) > 10
    assert abs(df["lai"].max() - 9.00) < 0.01
    assert abs(df["avg_temp_c"].max() - 24.30) < 0.01


def test_yld():
    """Read a slope file"""
    df = dep.read_yld(get_path("yld.txt"))
    assert len(df.index) == 10
    assert abs(df["yield_kgm2"].max() - 0.93) < 0.01


def test_slp():
    """Read a slope file"""
    slp = dep.read_slp(get_path("slp.txt"))
    assert len(slp) == 5
    assert abs(slp[4]["y"][-1] + 2.91) < 0.01
    assert abs(slp[4]["slopes"][-1] - 0.033) < 0.01


def test_man_rotation_repeats():
    """Test that a management file can have a rotation repeat read."""
    manfile = dep.read_man(get_path("man3.txt"))
    assert manfile["nrots"] == 2
    assert manfile["nyears"] == 14
    assert len(manfile["rotations"]) == 28


def test_man():
    """Read a management file please"""
    manfile = dep.read_man(get_path("man.txt"))
    assert manfile["nop"] == 5
    assert manfile["nini"] == 2
    assert manfile["nsurf"] == 2
    assert manfile["nwsofe"] == 3
    assert manfile["nrots"] == 1
    assert manfile["nyears"] == 11

    manfile = dep.read_man(get_path("man2.txt"))
    assert manfile["nop"] == 0


def test_ofe():
    """Read an OFE please"""
    df = dep.read_ofe(get_path("ofe.txt"))
    assert abs(df["precip"].max() - 107.56) < 0.01

    df = dep.read_ofe(get_path("ofe2.txt"))
    print(df["sedleave"].sum())
    assert abs(df["sedleave"].sum() - 400257.48) < 0.01


def test_wb():
    """read a WB file please"""
    df = dep.read_wb(get_path("wb.txt"))
    assert abs(df["precip"].max() - 162.04) < 0.01


def test_cli():
    """read a CLI file please"""
    df = dep.read_cli(get_path("cli.txt"))
    assert len(df.index) == 4018


def test_cli_rfactor():
    """read a CLI file please"""
    df = dep.read_cli(get_path("cli.txt"), compute_rfactor=True)
    assert abs(df["rfactor"].max() - 872.63) < 0.01
    assert (df.groupby(df.index.year).sum()["rfactor"].max() - 4276.60) < 0.01


def test_empty():
    """don't error out on an empty ENV"""
    df = dep.read_env(get_path("empty_env.txt"))
    assert df.empty


def test_read():
    """Read a ENV file"""
    df = dep.read_env(get_path("good_env.txt"))
    df2 = df[df["date"] == datetime.datetime(2010, 6, 5)]
    assert len(df2.index) == 1
    row = df2.iloc[0]
    assert row["runoff"] == 86.3


def test_rfactor_empty():
    """Test our R-factor code."""
    res = dep.rfactor([], [])
    assert res == 0


def test_rfactor_one():
    """Test our R-factor code."""
    # 1 inch rain over 1 hour
    res = dep.rfactor([1.0, 2.0], [0.0, 25.4])
    assert abs(res - 170.31) < 0.1


def test_rfactor_english():
    """Test our R-factor code."""
    # 1 inch rain over 1 hour
    res = dep.rfactor([1.0, 2.0], [0.0, 25.4], return_rfactor_metric=False)
    assert abs(res - 2.71) < 0.1


def test_man2df():
    """Test generation of DataFrame from management file."""
    mandict = dep.read_man(get_path("man3.txt"))
    df = dep.man2df(mandict)
    ans = "Soy_2194"
    assert df.query("year == 6 and ofe == 1").iloc[0]["crop_name"] == ans
    df = dep.man2df(mandict, year1=2007)
    assert df.query("year == 2012 and ofe == 1").iloc[0]["crop_name"] == ans
