"""Data Model for GAIRMET."""

# pylint: disable=too-few-public-methods
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# third party
from shapely.geometry import MultiLineString, Polygon


class AIRMETRecord(BaseModel):
    """A single AIRMET Record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    gml_id: str
    label: str
    status: str
    hazard_type: str
    valid_at: datetime
    weather_conditions: List[str]
    geom: Polygon


class FreezingLevelRecord(BaseModel):
    """A single FreezingLevel Record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    gml_id: str
    valid_at: datetime
    geom: MultiLineString
    level: Optional[int] = None
    lower_level: int
    upper_level: int


class GAIRMETModel(BaseModel):
    """A G-AIRMET."""

    valid_from: datetime
    valid_to: datetime
    issuetime: datetime
    airmets: List[AIRMETRecord] = Field(default_factory=list)
    freezing_levels: List[FreezingLevelRecord] = Field(default_factory=list)
