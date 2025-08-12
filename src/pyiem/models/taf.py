"""TAF Data Model."""
# pylint: disable=too-few-public-methods

from datetime import datetime
from typing import List, Optional

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
    level: Optional[int] = Field(None, ge=0, le=100000)


class TAFForecast(BaseModel):
    """A TAF forecast."""

    valid: datetime
    raw: str
    ftype: int = Field(..., ge=0, le=5)
    end_valid: Optional[datetime] = None
    sknt: Optional[int] = Field(default=None, ge=0, le=199)
    drct: Optional[int] = Field(default=None, ge=0, le=360)
    gust: Optional[int] = Field(default=None, ge=0, le=199)
    visibility: Optional[float] = Field(default=None, ge=0, le=6)
    presentwx: List[str] = Field(default_factory=list)
    sky: List[SkyCondition] = Field(default_factory=list)
    shear: Optional[WindShear] = None


class TAFReport(BaseModel):
    """A TAF Report consisting of forecasts."""

    station: str = Field(..., min_length=4, max_length=4)
    valid: datetime
    product_id: str = Field(..., min_length=28, max_length=35)
    observation: TAFForecast
    forecasts: List[TAFForecast] = Field(default_factory=list)
