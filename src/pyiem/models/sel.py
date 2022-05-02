"""Pydantic data model for SPC Watch (SEL)."""
# pylint: disable=too-few-public-methods

# third party
from pydantic import BaseModel, Field


class SELModel(BaseModel):
    """SPC Watch Probability."""

    typ: str = Field(..., description="Type of watch")
    num: int = Field(..., description="Watch number for the year")
