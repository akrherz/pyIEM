"""Pydantic data model for SPC Watch Probabilities (WWP)."""
# pylint: disable=too-few-public-methods

from typing import Optional

from pydantic import BaseModel, Field


class WWPModel(BaseModel):
    """SPC Watch Probability."""

    typ: str = Field(..., description="Type of watch")
    num: int = Field(..., description="Watch number for the year")
    tornadoes_2m: Optional[int] = Field(None, description="Tornadoes 2m")
    tornadoes_1m_strong: Optional[int] = Field(
        None, description="Tornadoes 1m strong"
    )
    wind_10m: Optional[int] = Field(None, description="Wind 10m")
    wind_1m_65kt: Optional[int] = Field(None, description="Wind 1m 65kt")
    hail_10m: Optional[int] = Field(None, description="Hail 10m")
    hail_1m_2inch: Optional[int] = Field(None, description="Hail 1m 2inch")
    hail_wind_6m: Optional[int] = Field(None, description="Hail wind 6m")
    max_hail_size: Optional[float] = Field(None, description="Max hail size")
    max_wind_gust_knots: Optional[int] = Field(
        None, description="Max wind gust knots"
    )
    max_tops_feet: Optional[int] = Field(None, description="Max tops feet")
    storm_motion_drct: Optional[int] = Field(
        None, description="Storm motion drct"
    )
    storm_motion_sknt: Optional[int] = Field(
        None, description="Storm motion sknt"
    )
    is_pds: bool = Field(..., description="Is PDS")
