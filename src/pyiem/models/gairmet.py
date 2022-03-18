"""Data Model for GAIRMET."""
# pylint: disable=too-few-public-methods
from typing import List
from datetime import datetime

# third party
from shapely.geometry import Polygon, MultiLineString
from pydantic import BaseModel


class AIRMETRecord(BaseModel):
    """A single AIRMET Record."""

    label: str
    status: str
    hazard_type: str
    valid_at: datetime
    weather_conditions: List[str]
    geom: Polygon

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class FreezingLevelRecord(BaseModel):
    """A single FreezingLevel Record."""

    valid_at: datetime
    geom: MultiLineString
    level: int

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class GAIRMETModel(BaseModel):
    """A G-AIRMET."""

    valid_from: datetime
    valid_to: datetime
    airmets: List[AIRMETRecord] = []
    freezing_levels: List[FreezingLevelRecord] = []
