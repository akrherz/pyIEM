"""
  Classes Representing various variables
"""
# pylint: disable=no-member
import numpy as np
from pyiem.exceptions import UnitsError


class basetype:
    """Base Object for all our vars"""

    def __init__(self, value, units):
        """constructor with value and units required"""
        if units.upper() not in self.known_units:
            raise UnitsError(
                f"unrecognized temperature unit: {units} "
                f"known: {self.known_units}"
            )
        self._units = units.upper()
        if isinstance(value, list):
            self._value = np.ma.array(value, mask=[v is None for v in value])
        else:
            self._value = value

    def get_units(self):
        """Returns the units for this current datatype

        Returns:
          (str): the unit of this datatype
        """
        return self._units


class mixingratio(basetype):
    """Mixing Ratio."""

    known_units = ["KG/KG"]

    def value(self, units):
        """Convert the value into the provided units"""
        if units.upper() not in mixingratio.known_units:
            raise UnitsError(
                f"unrecognized mixingratio unit: {units} "
                f"known: {mixingratio.known_units}"
            )
        if units.upper() == self._units:
            return self._value


class distance(basetype):
    """Distance"""

    known_units = ["SM", "MI", "M", "KM", "FT", "MM", "IN", "CM"]

    def value(self, units):
        """Convert to a value in the given units"""
        units = units.upper()
        if units not in distance.known_units:
            raise UnitsError(
                f"unrecognized distance unit: {units} "
                f"known: {distance.known_units}"
            )
        if units == self._units:
            return self._value

        # MKS
        if self._units in ["SM", "MI"]:
            meters = self._value * 1609.344
        elif self._units == "FT":
            meters = self._value / 3.28084
        elif self._units == "KM":
            meters = self._value * 1000.0
        elif self._units == "MM":
            meters = self._value / 1000.0
        elif self._units == "CM":
            meters = self._value / 100.0
        elif self._units == "IN":
            meters = self._value * 0.0254
        else:
            meters = self._value
        # Output
        if units in ["SM", "MI"]:
            return meters / 1609.344
        if units == "FT":
            return meters * 3.28084
        if units == "KM":
            return meters / 1000.0
        if units == "MM":
            return meters * 1000.0
        if units == "CM":
            return meters * 100.0
        if units == "IN":
            return meters / 0.0254
        return meters


class precipitation(basetype):
    """Precipitation"""

    known_units = ["IN", "CM", "MM"]

    def value(self, units):
        """Convert to a value in the given units"""
        units = units.upper()
        if units not in precipitation.known_units:
            raise UnitsError(
                f"unrecognized precipitation unit: {units} "
                "known: {precipitation.known_units}"
            )
        if units == self._units:
            return self._value

        # MKS
        if self._units == "IN":
            mm = self._value * 25.4
        elif self._units == "CM":
            mm = self._value * 10.0
        else:
            mm = self._value

        # Convert
        if units == "MM":
            return mm
        if units == "CM":
            return mm * 10.0
        return mm / 25.4


class speed(basetype):
    """Speed"""

    known_units = ["KT", "MPH", "MPS", "KMH", "KTS"]

    def value(self, units=None):
        """Convert to a value in the given units"""
        if units is None:
            units = self._units
        units = units.upper()
        if units not in speed.known_units:
            raise UnitsError(
                f"unrecognized speed unit: {units} known: {speed.known_units}"
            )
        if units == self._units:
            return self._value
        # MKS
        if self._units == "KMH":
            mps_value = self._value / 3.6
        elif self._units in ["KT", "KTS"]:
            mps_value = self._value * 0.514444
        elif self._units == "MPH":
            mps_value = self._value * 0.447000
        else:
            mps_value = self._value
        # return
        if units == "KMH":
            return mps_value * 3.6
        if units in ["KT", "KTS"]:
            return mps_value / 0.514444
        if units == "MPH":
            return mps_value / 0.447000
        return mps_value


class humidity(basetype):
    """Humidity, this is not as straight forward as the others"""

    known_units = ["%"]

    def value(self, units):
        """Convert to a value in the given units"""
        if units.upper() not in humidity.known_units:
            raise UnitsError(
                f"unrecognized humidity unit: {units} "
                f"known: {humidity.known_units}"
            )
        return self._value


class direction(basetype):
    """Direction from North"""

    known_units = ["DEG", "RAD"]

    def value(self, units):
        """Convert to a value in the given units"""
        if units.upper() not in direction.known_units:
            raise UnitsError(
                f"unrecognized direction unit: {units} "
                f"known: {direction.known_units}"
            )
        if units.upper() == self._units:
            return self._value

        if self._units == "DEG" and units.upper() == "RAD":
            return self._value * 3.1415926535897931 / 180.0
        return self._value * 180 / 3.1415926535897931


class pressure(basetype):
    """Pressure"""

    known_units = ["MB", "HPA", "IN", "PA"]

    def value(self, units):
        """Convert to a value in the given units"""
        if units.upper() not in pressure.known_units:
            raise UnitsError(
                f"unrecognized pressure unit: {units} "
                f"known: {pressure.known_units}"
            )
        if units.upper() == self._units:
            return self._value

        # MKS
        if self._units == "IN":
            mb_value = self._value * 33.86398
        elif self._units == "PA":
            mb_value = self._value / 100.0
        else:
            mb_value = self._value
        # Now convert
        if units.upper() in ["MB", "HPA"]:
            return mb_value
        if units.upper() == "PA":
            return mb_value * 100.0
        return mb_value / 33.86398


class temperature(basetype):
    """Temperature"""

    known_units = ["F", "K", "C"]

    def value(self, units):
        """Convert to a value in the given units"""
        units = units.upper()
        if units not in temperature.known_units:
            raise UnitsError(
                f"unrecognized temperature unit: {units} "
                f"known: {temperature.known_units}"
            )
        if units == self._units:
            return self._value

        # Convert to Celsius first
        if self._units == "C":
            celsius_value = self._value
        elif self._units == "F":
            celsius_value = (self._value - 32.0) / 1.8
        elif self._units == "K":
            celsius_value = self._value - 273.15
        # Dump back
        if units == "C":
            return celsius_value
        if units == "K":
            return 273.15 + celsius_value
        return 32.0 + celsius_value * 1.8
