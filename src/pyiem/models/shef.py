"""SHEF Data Model."""
# pylint: disable=too-few-public-methods

# stdlib
from datetime import datetime, timedelta

# third party
from pydantic import BaseModel, Field

# Local
from pyiem.reference import shef_send_codes, shef_table7


class SHEFElement(BaseModel):
    """A PEDTSEP Element."""

    station: str = Field(...)
    valid: datetime = Field(...)
    dv_interval: timedelta = Field(None)  # DV
    physical_element: str = Field(None, length=2)
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
