"""
 We do meteorological things, when necessary
"""
import math

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
    
    e  = 6.112 * math.exp( (17.67 * dwpc) / (dwpc + 243.5));
    es  = 6.112 * math.exp( (17.67 * tmpc) / (tmpc + 243.5));
    relh = ( e / es ) * 100.00;
    return relh

    