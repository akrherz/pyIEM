"""
 We do meteorological things, when necessary
"""
import numpy as np

def uv(speed, direction):
    """
    Compute the u and v components of the wind 
    @param wind speed in whatever units
    @param dir wind direction with zero as north
    @return u and v components
    """
    dirr = direction * np.pi / 180.00
    u = (0 - speed) * np.sin(dirr)
    v = (0 - speed) * np.cos(dirr)
    return u, v


def feelslike(temperature, dewpoint, speed):
    """
    Compute a feels like temperature
    """
    pass

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
    return relh

    