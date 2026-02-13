"""TAF Data Model."""

from datetime import datetime
from typing import Annotated, List, Optional

# third party
from pydantic import BaseModel, Field


class WindShear(BaseModel):
    """A Wind Shear Value."""

    level: Annotated[int, Field(ge=0, le=100000)]
    drct: Annotated[int, Field(ge=0, le=360)]
    sknt: Annotated[int, Field(ge=0, le=199)]


class SkyCondition(BaseModel):
    """The Sky condition."""

    amount: str
    level: Annotated[int | None, Field(ge=0, le=100000)] = None


class TAFForecast(BaseModel):
    """A TAF forecast."""

    valid: datetime
    raw: str
    ftype: Annotated[int, Field(ge=0, le=5)]
    end_valid: Optional[datetime] = None
    sknt: Annotated[int | None, Field(ge=0, le=199)] = None
    drct: Annotated[int | None, Field(ge=0, le=360)] = None
    gust: Annotated[int | None, Field(ge=0, le=199)] = None
    visibility: Annotated[float | None, Field(ge=0, le=6)] = None
    presentwx: List[str] = Field(default_factory=list)
    sky: List[SkyCondition] = Field(default_factory=list)
    shear: Optional[WindShear] = None


class TAFReport(BaseModel):
    """A TAF Report consisting of forecasts."""

    station: Annotated[str, Field(min_length=4, max_length=4)]
    valid: datetime
    product_id: Annotated[str, Field(min_length=28, max_length=35)]
    observation: TAFForecast
    is_amendment: Annotated[bool, Field(description="Is this amended?")]
    # Type checkers do not handle Annotated for this case
    forecasts: list[TAFForecast] = Field(default_factory=list)
