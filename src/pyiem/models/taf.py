"""TAF Data Model."""
# pylint: disable=too-few-public-methods

# stdlib
from datetime import datetime
from typing import List

# third party
from pydantic import BaseModel, Field


class WindShear(BaseModel):
    """A Wind Shear Value."""

    level: int = Field(..., ge=0, le=100000)
    drct: int = Field(..., ge=0, le=360)
    sknt: int = Field(..., ge=0, le=199)


class SkyCondition(BaseModel):
    """The Sky condition."""

    amount: str
    level: int = Field(..., ge=0, le=100000)


class TAFForecast(BaseModel):
    """A TAF forecast."""

    valid: datetime
    raw: str
    istempo: bool = False
    end_valid: datetime = None
    sknt: int = Field(None, ge=0, le=199)
    drct: int = Field(None, ge=0, le=360)
    gust: int = Field(None, ge=0, le=199)
    visibility: float = Field(None, ge=0, le=6)
    presentwx: List[str] = []
    sky: List[SkyCondition] = []
    shear: WindShear = None


class TAFReport(BaseModel):
    """A TAF Report consisting of forecasts."""

    station: str = Field(..., min_length=4, max_length=4)
    valid: datetime
    product_id: str = Field(..., min_length=28, max_length=35)
    observation: TAFForecast
    forecasts: List[TAFForecast] = []
