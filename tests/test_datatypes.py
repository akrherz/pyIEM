"""Test our pyiem.datatypes hack."""
import pytest
from pyiem import datatypes


def test_unitserror():
    """Make sure that unknown units actually raise an error"""
    for _, cls in datatypes.__dict__.items():
        if isinstance(cls, type) and hasattr(cls, "known_units"):
            a = cls(10, cls.known_units[0])
            with pytest.raises(datatypes.UnitsError):
                a.value("ZZzZZ")
            for unit in cls.known_units:
                a = cls(10, unit)
                for unit in cls.known_units:
                    assert a.value(unit) is not None


def test_mixingratio():
    """Mixing Ratio"""
    mixr = datatypes.mixingratio(10, "KG/KG")
    assert mixr.value("KG/KG") == 10


def test_temp_bad_units():
    """Simple check of bad units in temperature"""
    with pytest.raises(datatypes.UnitsError):
        datatypes.temperature(-99, "Q")


def test_temp_same_units():
    """Temperature data in equals data out"""
    value = 100.0
    tmpf = datatypes.temperature(value, "F")
    assert value == tmpf.value("F")


def test_temp_conv():
    """Temperature convert from Celsius to Fahrenheit to Kelvin"""
    c = datatypes.temperature(100.0, "C")
    assert 212 == c.value("F")
    assert 100.0 == c.value("C")
    assert 373.15 == c.value("K")


def test_press_conv():
    """Pressure convert from MB to IN to HPA"""
    hpa = datatypes.pressure(850.0, "HPA")
    assert 850.0 == hpa.value("MB")
    assert abs(25.10 - hpa.value("in")) < 0.01
    hpa = datatypes.pressure(85000.0, "PA")
    assert abs(25.10 - hpa.value("IN")) < 0.01


def test_speed_conv():
    """Speed convert from KT to MPS to KMH to MPH"""
    mph = datatypes.speed(58.0, "MPH")
    assert abs(50.4 - mph.value("KT")) < 0.1
    assert abs(25.93 - mph.value("mps")) < 0.01
    assert abs(93.33 - mph.value("KMH")) < 0.01


def test_precipitation_conv():
    """Speed precipitation from MM to CM to IN"""
    cm = datatypes.precipitation(25.4, "CM")
    assert abs(10.0 - cm.value("IN")) < 0.1
    assert abs(254.0 - cm.value("MM")) < 0.1


def test_distance_conv():
    """Speed distance from M to MI to FT to SM to KM"""
    mi = datatypes.distance(1.0, "mi")
    assert abs(1609.344 - mi.value("M")) < 0.1
    assert abs(5280.0 - mi.value("FT")) < 0.1
    assert abs(1.0 - mi.value("SM")) < 0.1
    assert abs(1.61 - mi.value("KM")) < 0.01
    assert abs(63360.00 - mi.value("IN")) < 0.01
    assert abs(1609344.00 - mi.value("mm")) < 0.01
    assert abs(160934.40 - mi.value("CM")) < 0.01


def test_direction_conv():
    """Direction, which is DEG to RAD"""
    mi = datatypes.direction(360, "DEG")
    assert abs(6.2831853 - mi.value("rad")) < 0.0001
    mi = datatypes.direction(3.14159, "RAD")
    assert abs(180.0 - mi.value("DEG")) < 0.01
