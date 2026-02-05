import re
from unittest.mock import MagicMock, patch

from icalendar import Calendar

from src.utils.ical import csv_to_ical
from src.utils.location import get_coordinates


def test_zip_comma_insertion():
    # Helper to test the regex logic used in ical_utils
    location = "Musterstraße 123 12345 Musterstadt"
    if "," not in location:
        location = re.sub(r"^(.*?)\s+(\d{5})\s+(.*)$", r"\1, \2 \3", location)
    assert location == "Musterstraße 123, 12345 Musterstadt"


@patch("src.utils.ical.get_coordinates")
def test_location_formatting_in_ical(mock_coords, tmp_path):
    mock_coords.return_value = (52.520, 13.405)

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location_name,location,place,name,description\n"
        "11.04.2026,09:00,8h,Bäckerei Musterstadt,Musterstraße 123 12345 Musterstadt,Germany,Test Event,Test Desc\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Test Cal")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    # Check LOCATION format (Name\nAddress)
    assert event.get("LOCATION") == "Bäckerei Musterstadt\nMusterstraße 123, 12345 Musterstadt, Germany"

    # Check GEO
    geo = event.get("GEO")
    assert geo.latitude == 52.520
    assert geo.longitude == 13.405

    # Check X-APPLE-STRUCTURED-LOCATION
    apple_loc = event.get("X-APPLE-STRUCTURED-LOCATION")
    assert str(apple_loc) == "geo:52.52,13.405"
    assert apple_loc.params.get("VALUE") == "URI"
    assert apple_loc.params.get("X-ADDRESS") == "Musterstraße 123, 12345 Musterstadt, Germany"
    assert apple_loc.params.get("X-TITLE") == "Bäckerei Musterstadt"
    assert apple_loc.params.get("X-APPLE-RADIUS") == "70"


@patch("src.utils.ical.get_coordinates")
def test_location_formatting_fallback_to_name(mock_coords, tmp_path):
    mock_coords.return_value = (52.520, 13.405)

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location_name,location,place,name,description\n"
        "11.04.2026,09:00,8h,,Musterstraße 123 12345 Musterstadt,Germany,Event Name,Test Desc\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Test Cal")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    # Should fallback to entry.name for venue name
    assert event.get("LOCATION") == "Event Name\nMusterstraße 123, 12345 Musterstadt, Germany"


def test_empty_location_handling(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location_name,location,place,name,description\n"
        "11.04.2026,09:00,8h,Some Venue,,,Event Name,Test Desc\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Test Cal")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    # Should only have venue name, no \n
    assert event.get("LOCATION") == "Some Venue"
    assert event.get("GEO") is None
    assert event.get("X-APPLE-STRUCTURED-LOCATION") is None


def test_geocode_cache_behavior():
    with patch("src.utils.location.Nominatim") as mock_nom:
        instance = mock_nom.return_value
        instance.geocode.return_value = MagicMock(latitude=1.0, longitude=2.0)

        # Reset lru_cache for test
        get_coordinates.cache_clear()

        coords1 = get_coordinates("Target Address")
        coords2 = get_coordinates("Target Address")

        assert coords1 == (1.0, 2.0)
        assert coords2 == (1.0, 2.0)
        assert instance.geocode.call_count == 1


def test_lru_cache_efficiency():
    with patch("src.utils.location.Nominatim") as mock_nom:
        instance = mock_nom.return_value
        instance.geocode.return_value = MagicMock(latitude=1.0, longitude=2.0)

        get_coordinates.cache_clear()

        # 1st call: Miss
        get_coordinates("Address A")
        # 2nd call: Hit
        get_coordinates("Address A")
        # 3rd call: Miss
        get_coordinates("Address B")

        info = get_coordinates.cache_info()
        assert info.hits == 1
        assert info.misses == 2
        assert info.currsize == 2
