"""
We do meteorological things, when necessary
"""

import math

import metpy.calc as mcalc
import numpy as np
from metpy.units import units

import pyiem.datatypes as dt
from pyiem.exceptions import InvalidArguments


def temperature_humidity_index(temperature, humidity):
    """Compute the Temperature Humidity Index

    Args:
      temperature (temperature): The Air Temperature
      humidity (humidity): The Relative Humidity

    Returns:
      temperature (temperature): The THI
    """
    tmpc = temperature.to(units("degC")).m
    rh = humidity.to(units("percent")).m
    return 0.8 * tmpc + (rh / 100.0) * (tmpc - 14.4) + 46.4


def comprehensive_climate_index(
    airtemp,
    rh,
    windspeed,
    solarrad,
    shade_effect: bool = False,
):
    """Compute the Comprehensive Climate Index.

    Note: shade_effect multiplies the ``solarrad`` value by 0.2 (80% reduction)
    """
    tmpc = airtemp.to(units("degC")).m
    rh = rh.to(units("percent")).m
    ws = windspeed.to(units("m/s")).m
    srad = solarrad.to(units("W/m^2")).m
    if shade_effect:
        srad *= 0.2
    term2 = (1.0 / np.power(2.26 * ws + 0.23, 0.45)) * (
        2.9
        + 0.000_001_14 * np.power(ws, 2.5)
        - np.log(np.power(2.26 * ws + 0.33, -2)) / np.log(0.3)
    )
    return (
        tmpc
        + (
            np.exp(0.00182 * rh + 0.000018 * tmpc * rh)
            * (0.000054 * tmpc * tmpc + 0.00192 * tmpc - 0.0246)
            * (rh - 30.0)
        )
        + (-6.56 / np.exp(term2) - 0.00566 * np.power(ws, 2) + 3.33)
        + (
            0.0076 * srad
            - 0.00002 * srad * tmpc
            + 0.00005 * tmpc * tmpc * np.sqrt(srad)
            + 0.1 * tmpc
            - 2.0
        )
    )


def clearsky_shortwave_irradiance_year(lat, elevation):
    """Compute the Clear Sky Shortwave Irradiance for year in MJ m**-2

    Args:
      lat (float): latitude
      elevation (float): location elevation in meters

    Returns:
      irradiance (list)
    """
    # Mean pressure in kPa
    pa = 101.3 * math.exp((0 - elevation) / 8200.0)
    # TOA radiation Wm**2
    spo = 1360.0
    # assume clearsky
    tau = 0.75
    # julian days
    j = np.arange(1, 366, 1)
    # solar declination
    _a = np.sin(np.radians(356.6 + 0.9856 * j))
    _b = np.sin(np.radians(278.97 + 0.9856 * j + 1.9165 * _a))
    delta = np.degrees(np.arcsin(0.39785 * _b))
    data = []
    for jday in j:
        running = 0
        for t in np.arange(0, 12.001, 5.0 / 60.0):
            _a = math.cos(np.radians(15 * (t - 12)))
            _b = math.sin(np.radians(lat))
            _c = math.sin(np.radians(delta[jday - 1]))
            theta = np.degrees(
                math.acos(
                    _b * _c
                    + math.cos(np.radians(lat))
                    * math.cos(np.radians(delta[jday - 1]))
                    * _a
                )
            )
            if theta >= 90:
                continue
            m = pa / (101.3 * math.cos(np.radians(theta)))
            direct = spo * tau**m * math.cos(np.radians(theta))
            diffuse = 0.3 * (1 - tau**m) * spo * math.cos(np.radians(theta))
            running += (5.0 * 60) * (direct + diffuse)
        data.append((running * 2.0) / 1000000.0)
    return data


def drct(u, v):
    """
    Compute the wind direction given a u and v wind speed

    Args:
      u (dt.speed): u component wind speed
      v (dt.speed): v component wind speed

    Returns:
      dt.direction value
    """
    umps = u.value("MPS")
    vmps = v.value("MPS")
    val = (np.arctan2(umps, vmps) * 180.0 / np.pi) + 180
    return dt.direction(val, "DEG")


def uv(speed, direction):
    """
    Compute the u and v components of the wind
    @param wind speed in whatever units
    @param dir wind direction with zero as north
    @return u and v components
    """
    if not isinstance(speed, dt.speed) or not isinstance(
        direction, dt.direction
    ):
        raise InvalidArguments(
            ("uv() needs speed and direction objects as args")
        )
    # Get radian units
    rad = direction.value("RAD")
    u = (0 - speed.value()) * np.sin(rad)
    v = (0 - speed.value()) * np.cos(rad)
    return (dt.speed(u, speed.get_units()), dt.speed(v, speed.get_units()))


def mcalc_feelslike(tmpf, dwpf, smps, mask_undefined=False):
    """Compute a feels like temperature

    Args:
      temperature (temperature): The dry bulb temperature
      dewpoint (temperature): The dew point temperature
      speed (speed): the wind speed
      mask_undefined (bool): If True, mask values where feels like is undef.

    Returns:
      temperature (temperature): The feels like temperature
    """
    is_scalar = not isinstance(tmpf.m, (list, tuple, np.ndarray))
    app = mcalc.apparent_temperature(
        tmpf,
        mcalc.relative_humidity_from_dewpoint(tmpf, dwpf),
        smps,
        mask_undefined=mask_undefined,
    )
    # Ensures we roundtrip a scalar
    return app[0] if is_scalar else app


def windchill(temperature, speed):
    """Compute the wind chill temperature

    http://www.ofcm.gov/publications/reports2.htm

    Args:
      temperature (temperature): The Air Temperature
      speed (speed): The Wind Speed

    Returns:
      temperature (temperature): The Wind Chill Temperature
    """
    tmpf = temperature.value("F")
    sknt = speed.value("KT")
    wci = (
        35.74
        + 0.6215 * tmpf
        - 35.75 * np.power(sknt, 0.16)
        + 0.4275 * tmpf * np.power(sknt, 0.16)
    )
    wci = np.where(
        np.logical_or(np.less(sknt, 3), np.greater(tmpf, 50)), tmpf, wci
    )
    return dt.temperature(wci, "F")


def heatindex(temperature, polyarg):
    """
    Compute the heat index based on

    Stull, Richard (2000). Meteorology for Scientists and Engineers,
    Second Edition. Brooks/Cole. p. 60. ISBN 9780534372149.

    Another opinion on appropriate equation:
    http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml

    http://www.weather.gov/media/ffc/ta_htindx.PDF
    """
    if not isinstance(temperature, dt.temperature):
        raise InvalidArguments("heatindex() needs temperature obj as arg")
    if isinstance(polyarg, dt.temperature):  # We have dewpoint
        polyarg = relh(temperature, polyarg)
    rh = polyarg.value("%")
    t = temperature.value("F")
    t2 = t**2
    t3 = t**3
    rh2 = rh**2
    rh3 = rh**3
    hdx = (
        16.923
        + ((1.85212e-1) * t)
        + (5.37941 * rh)
        - ((1.00254e-1) * t * rh)
        + ((9.41695e-3) * t2)
        + ((7.28898e-3) * rh2)
        + ((3.45372e-4) * t2 * rh)
        - ((8.14971e-4) * t * rh2)
        + ((1.02102e-5) * t2 * rh2)
        - ((3.8646e-5) * t3)
        + ((2.91583e-5) * rh3)
        + ((1.42721e-6) * t3 * rh)
        + ((1.97483e-7) * t * rh3)
        - ((2.18429e-8) * t3 * rh2)
        + ((8.43296e-10) * t2 * rh3)
        - ((4.81975e-11) * t3 * rh3)
    )
    hdx = np.where(np.logical_or(np.less(t, 80), np.greater(t, 120)), t, hdx)
    return dt.temperature(hdx, "F")


def dewpoint_from_pq(pressure, mixingratio):
    """
    Compute the Dew Point given a Pressure and Mixing Ratio
    """
    p = pressure.value("hPa")
    mr = mixingratio.value("kg/kg")
    e = (p * mr) / (0.622 + mr)
    b = 26.66082 - np.log(e)
    t = (b - (b * b - 223.1986) ** 0.5) / 0.0182758048
    return dt.temperature(t, "K")


def dewpoint(temperature, relhumid):
    """
    Compute Dew Point given a temperature and RH%
    """
    tmpk = temperature.value("K")
    _relh = relhumid.value("%")
    dwpk = tmpk / (1 + 0.000425 * tmpk * -(np.log10(_relh / 100.0)))
    return dt.temperature(dwpk, "K")


def relh(temperature, _dewpoint):
    """
    Compute Relative Humidity based on a temperature and dew point
    """
    # Get temperature in Celsius
    tmpc = temperature.value("C")
    dwpc = _dewpoint.value("C")

    e = 6.112 * np.exp((17.67 * dwpc) / (dwpc + 243.5))
    es = 6.112 * np.exp((17.67 * tmpc) / (tmpc + 243.5))
    _relh = (e / es) * 100.00
    return dt.humidity(_relh, "%")


def mixing_ratio(_dewpoint):
    """Compute the mixing ratio

    Args:
      dewpoint (temperature): Dew Point temperature

    Returns:
      mixing ratio
    """
    dwpc = _dewpoint.value("C")
    e = 6.112 * np.exp((17.67 * dwpc) / (dwpc + 243.5))
    return dt.mixingratio(0.62197 * e / (1000.0 - e), "KG/KG")


def gdd(high, low, base=50.0, ceiling=86.0):
    """Compute Growing Degree Days

    Args:
      high (temperature, or metpy.units): High Temperature
      low (temperature or metpy.units): Low Temperature
      base (int): Base to use in GDD Computation (F)
      ceiling (int): Ceiling to use in GDD Computation (F)

    Returns:
      float value for GDDs
    """
    if hasattr(high, "units"):
        highf = high.to(units("degF")).m
        lowf = low.to(units("degF")).m
    else:
        highf = high.value("F")
        lowf = low.value("F")
    highf = np.ma.where(np.ma.less(highf, base), base, highf)
    lowf = np.ma.where(np.ma.less(lowf, base), base, lowf)
    highf = np.ma.where(np.ma.greater(highf, ceiling), ceiling, highf)
    lowf = np.ma.where(np.ma.greater(lowf, ceiling), ceiling, lowf)
    res = (highf + lowf) / 2.0 - base
    if res.shape == (1,):
        return res[0]
    return res
