"""Data Model for IGRA."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import Point


class SoundingHeader(BaseModel):
    """A Center Weather Advisory."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    station: str
    valid: datetime
    release_valid: datetime
    p_src: str = Field(..., description="Pressure Source")
    np_src: str = Field(..., description="Number of Pressure Levels Source")
    geom: Point


class SoundingRecord(BaseModel):
    """Represents a sounding record."""

    # 0 should not be possible, but alas
    lvltyp1: int = Field(..., description="Level Type 1", ge=0, le=3)
    lvltyp2: int = Field(..., description="Level Type 2", ge=0, le=2)
    valid: Optional[datetime] = Field(None, description="Valid Time")
    press: Optional[float] = Field(None, description="Pressure", ge=0)
    pflag: str
    gph: Optional[int] = Field(None, description="Geopotential Height", ge=0)
    zflag: str
    temp: Optional[float] = Field(None, description="Temperature", ge=-100)
    tflag: str
    rh: Optional[float] = Field(
        None, description="Relative Humidity", gt=0, lt=105
    )
    dewp: Optional[float] = Field(
        None, description="Dewpoint Temperature", ge=-100
    )
    wdir: Optional[int] = Field(
        None, description="Wind Direction", ge=0, le=360
    )
    wspd: Optional[float] = Field(None, description="Wind Speed", ge=0)


class SoundingModel(BaseModel):
    """Represents a sounding."""

    header: SoundingHeader
    records: list[SoundingRecord]
