"""Pilot Report Data Model."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Types of reports."""

    def __str__(self):
        """When we want the str repr."""
        return str(self.value)

    UA = "UA"
    UUA = "UUA"


class PilotReport(BaseModel):
    """A Pilot Report."""

    base_loc: Optional[str] = None
    flight_level: Optional[int] = Field(
        default=None,
        description="The flight level of the aircraft in feet.",
        gt=0,
        lt=100000,  # 100k feet, arb
    )
    text: Optional[str] = None
    priority: Optional[Priority] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    valid: Optional[datetime] = None
    cwsu: Optional[str] = None
    aircraft_type: Optional[str] = None
    is_duplicate: bool = False
