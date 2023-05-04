"""Data Model for CWA."""
# pylint: disable=too-few-public-methods
from datetime import datetime

from pydantic import BaseModel

# third party
from shapely.geometry import Polygon


class CWAModel(BaseModel):
    """A Center Weather Advisory."""

    center: str
    expire: datetime
    geom: Polygon
    issue: datetime
    is_corrected: bool
    narrative: str
    num: int

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
