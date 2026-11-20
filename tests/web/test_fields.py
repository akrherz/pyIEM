"""Test pyiem.web.fields."""

import pytest
from pydantic import BaseModel, ValidationError

from pyiem.web import fields


@pytest.fixture
def station_model():
    """Return a basemodel for testing."""

    class Model(BaseModel):
        wfo: fields.WFO3_FIELD = "DMX"
        wfo4: fields.WFO4_FIELD = "KDMX"
        wfo_nt: fields.WFO_NT_FIELD = "DMX"
        station: fields.STATION_LIST_FIELD
        tz: fields.TZ_FIELD = "UTC"

    return Model


@pytest.mark.parametrize(
    "wfo_input,wfo_expected",
    [
        ("DMX", "DMX"),
        ("KDMX", "DMX"),
        ("PGUM", "PGUM"),
        ("PHFO", "PHFO"),
        ("TJSJ", "TJSJ"),
        ("NSTU", "NSTU"),
    ],
)
def test_rectify_wfo_nt(station_model, wfo_input, wfo_expected):
    """Test how WFO3_FIELD unrectifies four character WFOs."""
    assert station_model(wfo_nt=wfo_input, station="A").wfo_nt == wfo_expected


@pytest.mark.parametrize(
    "wfo_input,wfo_expected",
    [
        ("DMX", "DMX"),
        ("KDMX", "DMX"),
        ("PGUM", "GUM"),
        ("PHFO", "HFO"),
        ("PAFG", "AFG"),
        ("PAJK", "AJK"),
        ("PAFC", "AFC"),
        ("TJSJ", "JSJ"),
        ("TSJU", "JSJ"),
        ("NSTU", "STU"),
    ],
)
def test_unrectify_wfo(station_model, wfo_input, wfo_expected):
    """Test how WFO3_FIELD unrectifies four character WFOs."""
    assert station_model(wfo=wfo_input, station="A").wfo == wfo_expected


@pytest.mark.parametrize("invalid_input", ["D", "DM", "DMX0"])
def test_wfo_not_rectify_bad_input(station_model, invalid_input):
    """Test that WFO fields are the correct size."""
    with pytest.raises(ValidationError):
        station_model(wfo=invalid_input, station="A")
    with pytest.raises(ValidationError):
        station_model(wfo4=invalid_input, station="A")


@pytest.mark.parametrize(
    "wfo_input,wfo_expected",
    [
        ("DMX", "KDMX"),
        ("GUM", "PGUM"),
        ("STU", "NSTU"),
        ("PAFG", "PAFG"),
        ("JSJ", "TJSJ"),
        ("SJU", "TJSJ"),
        ("ABR", "KABR"),  # This is a life choice, since ABR conflicts
    ],
)
def test_rectify_wfo(station_model, wfo_input, wfo_expected):
    """Test how WFO4_FIELD rectifies three character WFOs."""
    assert station_model(wfo4=wfo_input, station="A").wfo4 == wfo_expected


def test_valid_tz(station_model):
    """Test that a valid timezone works."""
    ans = "America/New_York"
    assert station_model(station="A", tz=ans).tz == ans


def test_tz_aliases(station_model):
    """Test that these are handled."""
    assert station_model(station="A", tz="").tz == "UTC"
    assert station_model(station="A", tz="etc/utc").tz == "UTC"


def test_bad_tz(station_model):
    """Test that this fails validation."""
    with pytest.raises(ValidationError, match="Unknown timezone: BAD!TZ"):
        station_model(station="A", tz="BAD!TZ")


def test_no_station(station_model):
    """Test what happens when no station is provided"""
    with pytest.raises(ValidationError, match="Field required"):
        station_model()


def test_station_list_field(station_model):
    """Test the station list field."""
    assert station_model(station="DSM").station == ["DSM"]
    assert station_model(station="DSM, OMA").station == ["DSM", "OMA"]
    assert station_model(station=" DSM , oMA ").station == ["DSM", "OMA"]
    assert station_model(station=["DSM ", "OMA"]).station == ["DSM", "OMA"]


def test_naughty_station_list_field(station_model):
    """That that these fail validation"""
    with pytest.raises(ValueError, match="Invalid parameter"):
        station_model(station="DSM, OMA, BAD!STN")
    with pytest.raises(ValueError, match="Invalid parameter"):
        station_model(station="BAD!STN")
