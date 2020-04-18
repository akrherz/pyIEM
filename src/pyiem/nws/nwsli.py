"""National Weather Service Location Idenitifiers (NWSLI)

A class to store metadata associated with a NWSLI entry.
"""
from shapely.geometry import Point


class NWSLI:
    """National Weather Service Location Idenitifiers (NWSLI)"""

    def __init__(self, identifier, name=None, wfos=None, lon=0, lat=0):
        """Constructor

        Args:
          identifier(str): The string identifier for this NWSLI
          name(str, optional): The free-form text name of this location
          wfo(list, optional): The wfo(s) associated with this NWSLI
          lon(float, optional): The longitude in decimal degrees
          lat(float, optional): The latitude in decimal degress
        """
        self.id = identifier
        self.name = name
        self.wfos = wfos if wfos is not None else []
        self.geometry = Point([lon, lat])

    def get_name(self):
        """Return the name of this NWSLI, uses `self.id` if name is unset

        Returns:
            str: the name of this site
        """
        if self.name is None:
            return f"(({self.id}))"
        return self.name
