"""SHEF Data Model."""
# pylint: disable=too-few-public-methods

# stdlib
from datetime import datetime

# third party
from pydantic import BaseModel, Field


class SHEFElement(BaseModel):
    """A PEDTSEP Element."""

    station: str = Field(...)
    valid: datetime = Field(...)
    physical_element: str = Field(..., length=2)
    duration: str = Field(None)
    type: str = Field(None)
    source: str = Field(None)
    extremum: str = Field(None)
    probability: str = Field(None)
    str_value: str = Field(None)
    num_value: float = Field(None)
    data_created: datetime = Field(None)
