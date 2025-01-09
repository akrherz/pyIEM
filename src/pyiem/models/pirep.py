"""Pilot Report Data Model."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Priority(str, Enum):
    """Types of reports."""

    def __str__(self):
        """When we want the str repr."""
        return str(self.value)

    UA = "UA"
    UUA = "UUA"


class PilotReport(BaseModel):
    """A Pilot Report."""

    base_loc: str = None
    text: str = None
    priority: Priority = None
    latitude: float = None
    longitude: float = None
    valid: datetime = None
    cwsu: str = None
    aircraft_type: str = None
    is_duplicate: bool = False
