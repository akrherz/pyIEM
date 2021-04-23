"""Test HTML Generation."""

from pyiem import htmlgen


def test_make_select():
    """Test that we can generate a select."""
    htmlgen.make_select("", "", {"one": "two", "three": "four"})


def test_make_select_list():
    """Test that we can generate a select."""
    htmlgen.make_select("", "", {"one": "two", "three": ["four", "five"]})


def test_make_select_dict():
    """Test that we can generate a select."""
    htmlgen.make_select("", "", {"one": "two", "three": {"four": "five"}})


def test_station_select():
    """Test the generation of a station selector."""
    htmlgen.station_select("IA_ASOS", "DSM", "station", select_all=True)
