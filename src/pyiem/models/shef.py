"""SHEF Data Model."""
# pylint: disable=too-few-public-methods

# stdlib
from datetime import datetime, timedelta

# third party
from pydantic import BaseModel, Field

# Local
from pyiem.reference import shef_send_codes


class SHEFElement(BaseModel):
    """A PEDTSEP Element."""

    station: str = Field(...)
    valid: datetime = Field(...)
    dv_interval: timedelta = Field(None)  # DV
    physical_element: str = Field(None, length=2)
    duration: str = Field(None)
    type: str = Field(None)
    source: str = Field(None)
    extremum: str = Field(None)
    probability: str = Field(None)
    str_value: str = Field("")
    num_value: float = Field(None)
    data_created: datetime = Field(None)
    depth: int = Field(None)
    unit_convention: str = Field("E")  # DU
    qualifier: str = Field(None)  # DQ

    def consume_code(self, text):
        """Fill out element based on provided text."""
        # Ensure we have no cruft taging along
        text = text.strip().split()[0]
        if text.startswith("D"):
            # Reserved per 3.3.1
            raise ValueError(f"Cowardly refusing to set D {text}")
        # Over-ride for some special codes
        text = shef_send_codes.get(text, text)
        length = len(text)
        # Always present
        self.physical_element = text[:2]
        if length >= 3:
            self.duration = text[2]
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
