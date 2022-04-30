"""Pydantic data model for SPC Watch Probabilities (WWP)."""
# pylint: disable=too-few-public-methods

# third party
from pydantic import BaseModel, Field


class WWPModel(BaseModel):
    """SPC Watch Probability."""

    typ: str = Field(..., description="Type of watch")
    num: int = Field(..., description="Watch number for the year")
    tornadoes_2m: int = Field(None, description="Tornadoes 2m")
    tornadoes_1m_strong: int = Field(None, description="Tornadoes 1m strong")
    wind_10m: int = Field(None, description="Wind 10m")
    wind_1m_65kt: int = Field(None, description="Wind 1m 65kt")
    hail_10m: int = Field(None, description="Hail 10m")
    hail_1m_2inch: int = Field(None, description="Hail 1m 2inch")
    hail_wind_6m: int = Field(None, description="Hail wind 6m")
    max_hail_size: float = Field(None, description="Max hail size")
    max_wind_gust_knots: int = Field(None, description="Max wind gust knots")
    max_tops_feet: int = Field(None, description="Max tops feet")
    storm_motion_drct: int = Field(None, description="Storm motion drct")
    storm_motion_sknt: int = Field(None, description="Storm motion sknt")
    is_pds: bool = Field(..., description="Is PDS")
