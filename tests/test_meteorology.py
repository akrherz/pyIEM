"""Tests for the pyiem.meteorology library"""
import warnings

import pytest
import numpy as np
from metpy.units import units, masked_array

from pyiem import datatypes, meteorology
from pyiem.exceptions import InvalidArguments

warnings.simplefilter("ignore", RuntimeWarning)


def test_gdd_with_metpy_units():
    """Test that we can handle being provided metpy units."""
    # 62.33F 41F
    res = meteorology.gdd(units("degK") * 290, units("degC") * 5)
    assert abs(res - 6.16) < 0.01


def test_masked_feelslike():
    """Test that a masked array can be handled."""
    tmpf = units("degF") * np.ma.array([80.0, 90.0], mask=[False, True])
    dwpf = units("degF") * np.ma.array([70.0, 60.0])
    smps = units("meter per second") * np.ma.array([10.0, 20.0])
    meteorology.mcalc_feelslike(tmpf, dwpf, smps)


def test_vectorized():
    """See that heatindex and windchill can do lists"""
    temp = datatypes.temperature([0, 10], "F")
    sknt = datatypes.speed([30, 40], "MPH")
    val = meteorology.windchill(temp, sknt).value("F")
    assert abs(val[0] - -24.50) < 0.01


def test_vectorized2():
    """See that heatindex and windchill can do lists"""
    t = datatypes.temperature([80.0, 90.0], "F")
    td = datatypes.temperature([70.0, 60.0], "F")
    hdx = meteorology.heatindex(t, td)
    assert abs(hdx.value("F")[0] - 83.93) < 0.01


def test_vectorized3():
    """See that heatindex and windchill can do lists"""
    tmpf = units("degF") * np.array([80.0, 90.0])
    dwpf = units("degF") * np.array([70.0, 60.0])
    smps = units("meter per second") * np.array([10.0, 20.0])
    feels = meteorology.mcalc_feelslike(tmpf, dwpf, smps)
    assert abs(feels.to(units("degF")).m[0] - 83.15) < 0.01


def test_vectorized4():
    """See that heatindex and windchill can do lists"""
    tmpf = masked_array([80.0, np.nan], units("degF"), mask=[False, True])
    dwpf = units("degF") * np.array([70.0, 60.0])
    smps = units("meter per second") * np.array([10.0, 20.0])
    feels = meteorology.mcalc_feelslike(tmpf, dwpf, smps)
    assert abs(feels.to(units("degF")).magnitude[0] - 83.15) < 0.01
    assert feels.mask[1]


def test_gdd_with_nans():
    """Can we properly deal with nan's and not emit warnings?"""
    highs = np.ma.array([70, 80, np.nan, 90], mask=[False, False, True, False])
    lows = highs - 10
    r = meteorology.gdd(
        datatypes.temperature(highs, "F"),
        datatypes.temperature(lows, "F"),
        50,
        86,
    )
    assert np.ma.is_masked(r[2])


def test_gdd_unit_array():
    """Test what happens with length 1 arrays."""
    r = meteorology.gdd(
        datatypes.temperature(
            [
                86,
            ],
            "F",
        ),
        datatypes.temperature(
            [
                50,
            ],
            "F",
        ),
        50,
        86,
    )
    assert r == 18


def test_gdd():
    """Growing Degree Days"""
    r = meteorology.gdd(
        datatypes.temperature(86, "F"), datatypes.temperature(50, "F"), 50, 86
    )
    assert r == 18

    r = meteorology.gdd(
        datatypes.temperature(51, "F"), datatypes.temperature(49, "F"), 50, 86
    )
    assert abs(r - 0.5) < 0.1

    r = meteorology.gdd(
        datatypes.temperature(49, "F"), datatypes.temperature(40, "F"), 50, 86
    )
    assert r == 0

    r = meteorology.gdd(
        datatypes.temperature([86, 86], "F"),
        datatypes.temperature([50, 50], "F"),
        50,
        86,
    )
    assert r[0] == 18
    assert r[1] == 18


def test_mixingratio():
    """Test the mixing ratio calculation"""
    r = meteorology.mixing_ratio(datatypes.temperature(70, "F"))
    assert abs(r.value("KG/KG") - 0.016) < 0.001


def test_sw():
    """Test shortwave flux calculation"""
    r = meteorology.clearsky_shortwave_irradiance_year(42, 100)
    assert abs(r[0] - 7.20) < 0.01
    assert abs(r[90] - 22.45) < 0.01
    assert abs(r[182] - 32.74) < 0.01
    assert abs(r[270] - 19.07) < 0.01
    assert abs(r[364] - 7.16) < 0.01


def test_drct():
    """Conversion of u and v to direction"""
    r = meteorology.drct(
        datatypes.speed(np.array([10, 20]), "KT"),
        datatypes.speed(np.array([10, 20]), "KT"),
    ).value("DEG")
    assert r[0] == 225
    r = meteorology.drct(
        datatypes.speed(-10, "KT"), datatypes.speed(10, "KT")
    ).value("DEG")
    assert r == 135
    r = meteorology.drct(
        datatypes.speed(-10, "KT"), datatypes.speed(-10, "KT")
    ).value("DEG")
    assert r == 45
    r = meteorology.drct(
        datatypes.speed(10, "KT"), datatypes.speed(-10, "KT")
    ).value("DEG")
    assert r == 315


def test_windchill():
    """Wind Chill Conversion"""
    temp = datatypes.temperature(0, "F")
    sknt = datatypes.speed(30, "MPH")
    val = meteorology.windchill(temp, sknt).value("F")
    assert abs(val - -24.50) < 0.01


def test_dewpoint_from_pq():
    """See if we can produce dew point from pressure and mixing ratio"""
    p = datatypes.pressure(1013.25, "MB")
    mr = datatypes.mixingratio(0.012, "kg/kg")
    dwpk = meteorology.dewpoint_from_pq(p, mr)
    assert abs(dwpk.value("C") - 16.84) < 0.01


def test_dewpoint():
    """test out computation of dew point"""
    for t0, r0, a0 in [[80, 80, 73.42], [80, 20, 35.87]]:
        t = datatypes.temperature(t0, "F")
        rh = datatypes.humidity(r0, "%")
        dwpk = meteorology.dewpoint(t, rh)
        assert abs(dwpk.value("F") - a0) < 0.01


def test_headindex_invalidargs():
    """Test that we handle invalid args."""
    bogus = datatypes.speed(10, "KT")
    td = datatypes.temperature(70.0, "F")
    with pytest.raises(InvalidArguments):
        meteorology.heatindex(bogus, td)


def test_heatindex():
    """Test our heat index calculations"""
    t = datatypes.temperature(80.0, "F")
    td = datatypes.temperature(70.0, "F")
    hdx = meteorology.heatindex(t, td)
    assert abs(hdx.value("F") - 83.93) < 0.01

    t = datatypes.temperature(30.0, "F")
    hdx = meteorology.heatindex(t, td)
    assert abs(hdx.value("F") - 30.00) < 0.01


def test_uv_invalid_args():
    """Test code that checks units."""
    bogus = datatypes.temperature([10], "K")
    mydir = datatypes.direction([0], "DEG")
    with pytest.raises(InvalidArguments):
        meteorology.uv(bogus, mydir)


def test_uv():
    """Test calculation of uv wind components"""
    speed = datatypes.speed([10], "KT")
    mydir = datatypes.direction([0], "DEG")
    u, v = meteorology.uv(speed, mydir)
    assert u.value("KT") == 0.0
    assert v.value("KT") == -10.0

    speed = datatypes.speed([10, 20, 15], "KT")
    mydir = datatypes.direction([90, 180, 135], "DEG")
    u, v = meteorology.uv(speed, mydir)
    assert u.value("KT")[0] == -10
    assert v.value("KT")[1] == 20.0
    assert abs(v.value("KT")[2] - 10.6) < 0.1


def test_relh():
    """Simple check of bad units in temperature"""
    tmp = datatypes.temperature(24, "C")
    dwp = datatypes.temperature(24, "C")
    relh = meteorology.relh(tmp, dwp)
    assert relh.value("%") == 100.0

    tmp = datatypes.temperature(32, "C")
    dwp = datatypes.temperature(10, "C")
    relh = meteorology.relh(tmp, dwp)
    assert abs(25.79 - relh.value("%")) < 0.01

    tmp = datatypes.temperature(32, "C")
    dwp = datatypes.temperature(15, "C")
    relh = meteorology.relh(tmp, dwp)
    assert abs(35.81 - relh.value("%")) < 0.01

    tmp = datatypes.temperature(5, "C")
    dwp = datatypes.temperature(4, "C")
    relh = meteorology.relh(tmp, dwp)
    assert abs(93.24 - relh.value("%")) < 0.01
