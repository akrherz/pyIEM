"""
 We do meteorological things, when necessary
"""
import numpy as np
import pyiem.datatypes as dt

class InvalidArguments(Exception):
    pass

def drct(u, v):
    """
    Compute the wind direction given a u and v wind speed
    """
    return 0 #TODO
    if (v.value):
        val = 1
    
    return dt.direction(val, 'DEG')

def uv(speed, direction):
    """
    Compute the u and v components of the wind 
    @param wind speed in whatever units
    @param dir wind direction with zero as north
    @return u and v components
    """
    if not isinstance(speed, dt.speed) or not isinstance(direction, dt.direction):
        raise InvalidArguments("uv() needs speed and direction objects as args")
    # Get radian units
    rad = direction.value("RAD")
    u = (0 - speed.value()) * np.sin(rad)
    v = (0 - speed.value()) * np.cos(rad)
    return dt.speed(u, speed._units), dt.speed(v, speed._units)


def feelslike(temperature, dewpoint, speed):
    """
    Compute a feels like temperature
    """
    pass

def heatindex(temperature, polyarg):
    """
    Compute the heat index based on
    
    Stull, Richard (2000). Meteorology for Scientists and Engineers, 
    Second Edition. Brooks/Cole. p. 60. ISBN 9780534372149.
    
    Another opinion on appropriate equation:
    http://www.hpc.ncep.noaa.gov/html/heatindex_equation.shtml
    """
    if not isinstance(temperature, dt.temperature): 
        raise InvalidArguments("heatindex() needs temperature obj as first arg")
    if isinstance(polyarg, dt.temperature): # We have dewpoint
        polyarg = relh(temperature, polyarg)
    rh = polyarg.value("%")
    t = temperature.value("F")
    if t < 60 or t > 120:
        return temperature
    hdx = (16.923 
             + ((1.85212e-1)*t)
             + (5.37941*rh)
             -((1.00254e-1)*t*rh) 
             +((9.41695e-3)*t**2)
             +((7.28898e-3)*rh**2)
             +((3.45372e-4)*t**2*rh)
             -((8.14971e-4)*t*rh**2)
             +((1.02102e-5)*t**2*rh**2)
             -((3.8646e-5)*t**3)
             +((2.91583e-5)*rh**3)
             +((1.42721e-6)*t**3*rh)
             +((1.97483e-7)*t*rh**3)
             -((2.18429e-8)*t**3*rh**2)
             +((8.43296e-10)*t**2*rh**3)
             -((4.81975e-11)*t**3*rh**3))
    return dt.temperature(hdx, 'F')
    
def dewpoint(temperature, relhumid):
    """
    Compute Dew Point given a temperature and RH%
    """
    tmpk = temperature.value("K")
    relh = relhumid.value("%")
    dwpk = tmpk / (1+ 0.000425 * tmpk * -(np.log10(relh/100.0)) )
    return dt.temperature(dwpk, 'K')

def relh(temperature, dewpoint):
    """
    Compute Relative Humidity based on a temperature and dew point
    """
    # Get temperature in Celsius
    tmpc = temperature.value("C")
    dwpc = dewpoint.value("C")
    
    e  = 6.112 * np.exp( (17.67 * dwpc) / (dwpc + 243.5))
    es  = 6.112 * np.exp( (17.67 * tmpc) / (tmpc + 243.5))
    relh = ( e / es ) * 100.00
    return dt.humidity(relh, '%')

    