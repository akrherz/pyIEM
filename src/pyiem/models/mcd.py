"""Storage of MCD stuff."""

from typing import Optional

from pydantic import BaseModel, Field


class MostProbableTags(BaseModel):
    hail: Optional[str] = Field(None, description="Hail")
    tornado: Optional[str] = Field(None, description="Tornado")
    gust: Optional[str] = Field(None, description="Wind Gust")
