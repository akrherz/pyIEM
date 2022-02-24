"""SHEF Data Model."""
# pylint: disable=too-few-public-methods

# stdlib
from datetime import datetime, timedelta

# third party
from pydantic import BaseModel, Field
from metpy.units import units

# Local
from pyiem.reference import (
    shef_send_codes,
    shef_table7,
    shef_english_units,
    shef_standard_units,
)
from pyiem.util import LOG

# Manually defined and used within shef_{english,standard}_units.txt
units.define("KCFS = 1000 * feet ^ 3 / second")
units.define("MCM = 1000000 * meter ^ 3")
units.define("DEG10 = 10 * degree")  # UH, UR


class SHEFElement(BaseModel):
    """A PEDTSEP Element."""

    station: str = Field(...)
    basevalid: datetime = Field(...)  # Prevent multiple DH24 from trouble
    valid: datetime = Field(...)
    dv_interval: timedelta = Field(None)  # DV
    physical_element: str = Field(None)  # PE
    duration: str = Field(None)
    type: str = Field("R")  # Table 7
    source: str = Field("Z")  # Table 7
    extremum: str = Field("Z")  # Table 7
    probability: str = Field("Z")  # Table 7
    str_value: str = Field("")
    num_value: float = Field(None)
    data_created: datetime = Field(None)
    depth: int = Field(None)
    unit_convention: str = Field("E")  # DU
    qualifier: str = Field(None)  # DQ
    comment: str = Field(None)  # This is found after the value
    narrative: str = Field(None)  # Free text after some Wxcoder/IVROCS
    raw: str = Field(None)  # The SHEF message

    def to_english(self) -> float:
        """Return an English value representation.

        Implementation Note: In the case of wind direction (UH, UR), this
        returns the un-scaled value.
        """
        if (
            self.physical_element in ["UH", "UR"]
            and self.num_value is not None
        ):
            return self.num_value * 10
        # NOOP
        if self.unit_convention == "E" or self.num_value is None:
            return self.num_value
        # We have work to do.
        ename = shef_english_units.get(self.physical_element)
        sname = shef_standard_units.get(self.physical_element)
        if ename is None or sname is None:
            LOG.warning("Unknown unit conv %s", self.physical_element)
            return self.num_value
        return (units(sname) * self.num_value).to(units(ename)).m

    def varname(self) -> str:
        """Return the Full SHEF Code."""
        if self.physical_element is None or self.duration is None:
            return None
        return (
            f"{self.physical_element}{self.duration}{self.type}{self.source}"
            f"{self.extremum}{self.probability}"
        )

    def consume_code(self, text):
        """Fill out element based on provided text."""
        # Ensure we have no cruft taging along
        text = text.strip().split()[0]
        if text.startswith("D"):
            # Reserved per 3.3.1
            raise ValueError(f"Cowardly refusing to set D {text}")
        if len(text) < 2:
            raise ValueError(f"text needs to be at least 2 chars {text}")
        # Table 2: Override for some special codes
        text = shef_send_codes.get(text, text)
        length = len(text)
        # Always present
        self.physical_element = text[:2]
        if length >= 3:
            self.duration = text[2]
        else:
            # SHEF Manual Table 7 provides duration defaults
            self.duration = shef_table7.get(self.physical_element, "I")
        if length >= 4:
            self.type = text[3]
        if length >= 5:
            self.source = text[4]
        if length >= 6:
            self.extremum = text[5]
        if length >= 7:
            self.probability = text[6]

        # 4.4.3 has to be a V, or else
        if self.dv_interval and self.duration != "V":
            self.dv_interval = None

    def lonlat(self):
        """For 'Stranger Locations', return longitude and latitude."""
        # 4.1.2  Must be 8 char
        char0 = self.station[0]
        if (
            len(self.station) != 8
            or char0 not in ["W", "X", "Y", "Z"]
            or any(x.isalpha() for x in self.station[1:])
        ):
            return None, None
        lat = float(self.station[1:4]) / 10.0
        lon = float(self.station[4:]) / 10.0
        if char0 in ["W", "X"]:
            lon *= -1
        if char0 in ["W", "Z"]:
            lat *= -1
        return lon, lat
