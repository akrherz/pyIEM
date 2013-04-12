"""
  Classes Representing various variables
"""

class UnitsError(Exception):
    """ Exception for bad Units """
    pass

class basetype(object):
    """ Base Object for all our vars """

    def __init__(self, value, units):
        """ constructor with value and units required """
        if units.upper() not in self.known_units:
            raise UnitsError("unrecognized temperature unit: %s known: %s" % (
                                units, self.known_units))
        self._units = units.upper()
        self._value = value

class distance(basetype):
    """ Distance """
    known_units = [ "SM", "MI", "M", "KM", "FT" ]
    
    def value(self, units):
        """ Convert to a value in the given units """
        if units.upper() not in distance.known_units:
            raise UnitsError("unrecognized distance unit: %s known: %s" % (
                                units, distance.known_units))
        if units.upper() == self._units:
            return self._value   

        # MKS
        if self._units in ["SM", "MI"]:
            meters = self._value * 1609.344
        elif self._units == "FT":
            meters = self._value / 3.28084
        elif self._units == "KM":
            meters = self._value * 1000.0
        else:
            meters = self._value
        # Output
        if units in ["SM","MI"]:
            return meters / 1609.344
        elif units == "FT":
            return meters * 3.28084
        elif units == "KM":
            return meters / 1000.0
        elif units == "M":
            return meters


class precipitation(basetype):
    """ Precipitation """
    known_units = ['IN', 'CM', 'MM']

    def value(self, units):
        """ Convert to a value in the given units """
        if units.upper() not in precipitation.known_units:
            raise UnitsError("unrecognized precipitation unit: %s known: %s" % (
                                units, precipitation.known_units))
        if units.upper() == self._units:
            return self._value
        
        # MKS
        if self._units == 'IN':
            mm = self._value * 25.4
        elif self._units == 'CM':
            mm = self._value * 10.0
        else:
            mm = self._value
            
        # Convert
        if units == 'MM':
            return mm
        elif units == 'CM':
            return mm * 10.0
        elif units == 'IN':
            return mm / 25.4
        
class speed(basetype):
    """ Speed """
    known_units = ['KT', 'MPH', 'MPS', 'KMH']

    def value(self, units):
        """ Convert to a value in the given units """
        if units.upper() not in speed.known_units:
            raise UnitsError("unrecognized speed unit: %s known: %s" % (
                                units, speed.known_units))
        if units.upper() == self._units:
            return self._value
        # MKS
        if self._units == "KMH":
            mps_value = self._value / 3.6
        elif self._units == "KT":
            mps_value = self._value * 0.514444
        elif self._units == "MPH":
            mps_value = self._value * 0.447000
        else:
            mps_value = self._value
        # return
        if units == "KMH":
            return mps_value * 3.6
        elif units == "KT":
            return mps_value / 0.514444
        elif units == "MPH":
            return mps_value / 0.447000
        elif units == "MPS":
            return mps_value



class pressure(basetype):
    """ Pressure """
    known_units = ['MB', 'HPA', 'IN']

    def value(self, units):
        """ Convert to a value in the given units """
        if units.upper() not in pressure.known_units:
            raise UnitsError("unrecognized pressure unit: %s known: %s" % (
                                units, pressure.known_units))
        if units.upper() == self._units:
            return self._value
        
        # MKS
        if self._units == "IN":
            mb_value = self._value * 33.86398
        else:
            mb_value = self._value
        # Now convert
        if units in ["MB","HPA"]:
            return mb_value
        elif units == "IN":
            return mb_value / 33.86398


class temperature(basetype):
    """ Temperature """
    known_units = ['F', 'K', 'C']
            
    def value(self, units):
        """ Convert to a value in the given units """
        if units.upper() not in temperature.known_units:
            raise UnitsError("unrecognized temperature unit: %s known: %s" % (
                                units, temperature.known_units))
        if units.upper() == self._units:
            return self._value
        
        # Convert to Celsius first
        if self._units == 'C':
            celsius_value = self._value
        elif self._units == 'F':
            celsius_value = (self._value -32.0) / 1.8
        elif self._units == 'K':
            celsius_value = self._value - 273.15
        # Dump back
        if units == "C":
            return celsius_value
        elif units == "K":
            return 273.15 + celsius_value
        elif units == "F":
            return 32.0 + celsius_value * 1.8
