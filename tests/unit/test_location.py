import re
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from icalendar import Calendar

import src.utils.location as loc_module
from src.utils.ical import csv_to_ical
from src.utils.location import format_address, get_coordinates
from src.utils.time import parse_duration


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


# --- format_address tests ---


def test_format_address_with_zip_no_comma():
    result = format_address("Musterstraße 123 12345 Musterstadt", "Germany")
    assert result == "Musterstraße 123, 12345 Musterstadt, Germany"


def test_format_address_with_existing_comma():
    # Already has a comma — should not double-insert
    result = format_address("Musterstraße 123, 12345 Musterstadt", "Germany")
    assert result == "Musterstraße 123, 12345 Musterstadt, Germany"


def test_format_address_empty_address_with_place():
    result = format_address("", "Germany")
    assert result == "Germany"


def test_format_address_with_address_no_place():
    result = format_address("Some Street 1", "")
    assert result == "Some Street 1"


def test_format_address_both_empty():
    result = format_address("", "")
    assert result == ""


def test_format_address_no_zip_code():
    # Address without a 5-digit zip: no comma insertion should occur
    result = format_address("Bahnhofstraße 1 Berlin", "Germany")
    assert result == "Bahnhofstraße 1 Berlin, Germany"


# --- get_coordinates tests ---


def test_get_coordinates_disabled(monkeypatch):
    from src.settings import settings

    monkeypatch.setattr(settings, "geocode_enabled", False)
    get_coordinates.cache_clear()
    result = get_coordinates("Anywhere")
    assert result is None


def test_get_coordinates_geocoder_returns_none():
    with patch("src.utils.location.Nominatim") as mock_nom:
        instance = mock_nom.return_value
        instance.geocode.return_value = None

        get_coordinates.cache_clear()
        result = get_coordinates("Unknown Place")
        assert result is None


def test_get_coordinates_geocoder_raises_exception():
    with patch("src.utils.location.Nominatim") as mock_nom:
        instance = mock_nom.return_value
        instance.geocode.side_effect = Exception("network error")

        get_coordinates.cache_clear()
        result = get_coordinates("Broken Address")
        assert result is None


# --- Nominatim rate-limiting tests ---


def test_rate_limiting_enforces_interval():
    """_throttle_geocode sleeps for the remainder of the interval when called too soon.

    _throttle_geocode calls time.monotonic() twice per invocation:
    once to check elapsed time, once to record the call timestamp.
    """
    sleep_calls: list[float] = []

    # Simulate: last call was at t=0, current time is t=0.3.
    # Expected sleep = 1.0 - (0.3 - 0.0) = 0.7 s.
    # monotonic returns: [0.3 (now), 1.0 (after sleep, to record new _last_geocode_time)]
    with patch("src.utils.location.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        with patch("src.utils.location.time.monotonic", side_effect=[0.3, 1.0]):
            loc_module._last_geocode_time = 0.0
            loc_module._throttle_geocode()

    assert len(sleep_calls) == 1
    assert abs(sleep_calls[0] - 0.7) < 0.01, f"Expected sleep ≈0.7 s, got {sleep_calls[0]}"


def test_rate_limiting_no_sleep_when_interval_elapsed():
    """_throttle_geocode must not sleep when enough time has already passed."""
    sleep_calls: list[float] = []

    # Simulate: last call at t=0, current time t=1.5 → no sleep needed.
    # monotonic returns: [1.5 (now), 1.5 (record new timestamp)]
    with patch("src.utils.location.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        with patch("src.utils.location.time.monotonic", side_effect=[1.5, 1.5]):
            loc_module._last_geocode_time = 0.0
            loc_module._throttle_geocode()

    assert sleep_calls == [], f"Expected no sleep, got {sleep_calls}"


def test_rate_limiter_called_on_cache_miss():
    """_throttle_geocode must be called exactly once per cache-miss geocode call."""
    with patch("src.utils.location.Nominatim") as mock_nom:
        instance = mock_nom.return_value
        instance.geocode.side_effect = [
            MagicMock(latitude=1.0, longitude=2.0),
            MagicMock(latitude=3.0, longitude=4.0),
        ]

        get_coordinates.cache_clear()

        with patch.object(loc_module, "_throttle_geocode") as mock_throttle:
            get_coordinates("Address X")
            get_coordinates("Address Y")

        # Two distinct addresses → two cache misses → two throttle calls
        assert mock_throttle.call_count == 2
        assert instance.geocode.call_count == 2


def test_rate_limiter_not_called_on_cache_hit():
    """A second call for the same address (cache hit) must not invoke _throttle_geocode."""
    with patch("src.utils.location.Nominatim") as mock_nom:
        instance = mock_nom.return_value
        instance.geocode.return_value = MagicMock(latitude=1.0, longitude=2.0)

        get_coordinates.cache_clear()

        with patch.object(loc_module, "_throttle_geocode") as mock_throttle:
            get_coordinates("Same Address")  # cache miss → throttle called
            get_coordinates("Same Address")  # cache hit → throttle NOT called

        assert mock_throttle.call_count == 1  # only the first (cache-miss) call
        assert instance.geocode.call_count == 1


def test_rate_limiter_skipped_when_geocoding_disabled(monkeypatch):
    """When geocoding is disabled, _throttle_geocode must never be called."""
    from src.settings import settings

    monkeypatch.setattr(settings, "geocode_enabled", False)
    get_coordinates.cache_clear()

    with patch.object(loc_module, "_throttle_geocode") as mock_throttle:
        result = get_coordinates("Anywhere")

    assert result is None
    mock_throttle.assert_not_called()


def test_first_geocode_call_does_not_sleep():
    """The very first geocode call after module load must not incur a sleep."""
    sleep_calls: list[float] = []
    # Set _last_geocode_time to its initial module-load value
    loc_module._last_geocode_time = -loc_module._MIN_GEOCODE_INTERVAL

    with patch("src.utils.location.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        with patch("src.utils.location.time.monotonic", return_value=0.0):
            loc_module._throttle_geocode()

    assert sleep_calls == [], f"First call should not sleep, got {sleep_calls}"


# --- parse_duration tests ---


def test_parse_duration_minutes():
    assert parse_duration("30min") == timedelta(minutes=30)


def test_parse_duration_hours():
    assert parse_duration("2h") == timedelta(hours=2)


def test_parse_duration_days():
    assert parse_duration("3d") == timedelta(days=3)


def test_parse_duration_zero_minutes():
    assert parse_duration("0min") == timedelta(minutes=0)


def test_parse_duration_unknown_format_returns_zero():
    # Unrecognized format (no recognised suffix) should return timedelta(minutes=0)
    # Note: strings ending in 'd', 'h', or 'min' are handled by those branches;
    # a truly unrecognised suffix (e.g. 's') falls through to the default.
    result = parse_duration("60s")
    assert result == timedelta(minutes=0)


def test_parse_duration_invalid_suffix_ending_in_d_raises():
    # A string ending in 'd' with a non-integer prefix raises ValueError —
    # this documents the current behaviour of the source code.
    with pytest.raises(ValueError):
        parse_duration("invalidd")


def test_parse_duration_large_value():
    assert parse_duration("1440min") == timedelta(minutes=1440)
    assert parse_duration("24h") == timedelta(hours=24)


# --- csv_to_ical edge cases ---


@patch("src.utils.ical.get_coordinates")
def test_uid_uniqueness_across_events(mock_coords, tmp_path):
    mock_coords.return_value = None

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location,name,description\n"
        "01.01.2025,10:00,1h,Venue A,Event One,Desc A\n"
        "02.01.2025,10:00,1h,Venue B,Event Two,Desc B\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Test Cal")
    cal = Calendar.from_ical(ical_bytes)
    events = cal.walk("VEVENT")
    uids = [str(e.get("UID")) for e in events]
    assert len(uids) == 2
    assert uids[0] != uids[1]


@patch("src.utils.ical.get_coordinates")
def test_uid_deterministic_for_same_event(mock_coords, tmp_path):
    mock_coords.return_value = None

    csv_content = (
        "date,time,duration,location,name,description\n05.06.2025,14:00,2h,Somewhere,My Event,Some description\n"
    )

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    ical1 = csv_to_ical(csv_file, "Cal")
    ical2 = csv_to_ical(csv_file, "Cal")
    cal1 = Calendar.from_ical(ical1)
    cal2 = Calendar.from_ical(ical2)
    uid1 = str(cal1.walk("VEVENT")[0].get("UID"))
    uid2 = str(cal2.walk("VEVENT")[0].get("UID"))
    assert uid1 == uid2


@patch("src.utils.ical.get_coordinates")
def test_geocoding_disabled_no_geo_field(mock_coords, tmp_path):
    """When get_coordinates returns None (e.g. geocoding disabled), GEO and
    X-APPLE-STRUCTURED-LOCATION fields must not appear on the event."""
    mock_coords.return_value = None

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location,name,description\n10.10.2025,09:00,1h,Berlin Mitte,Some Event,Details\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Test Cal")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    assert event.get("GEO") is None
    assert event.get("X-APPLE-STRUCTURED-LOCATION") is None


@patch("src.utils.ical.get_coordinates")
def test_timed_event_has_datetime_dtstart(mock_coords, tmp_path):
    from datetime import datetime

    mock_coords.return_value = None

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location,name,description\n15.03.2025,08:30,90min,Office,Morning Standup,Daily sync\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Work")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    dtstart = event.get("DTSTART").dt
    # Timed event should have a datetime, not a date
    assert isinstance(dtstart, datetime)


@patch("src.utils.ical.get_coordinates")
def test_allday_event_has_date_dtstart(mock_coords, tmp_path):
    from datetime import date, datetime

    mock_coords.return_value = None

    csv_file = tmp_path / "test.csv"
    csv_file.write_text("date,time,duration,location,name,description\n25.12.2025,00:00,1d,,Christmas,Public holiday\n")

    ical_bytes = csv_to_ical(csv_file, "Holidays")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    dtstart = event.get("DTSTART").dt
    assert isinstance(dtstart, date)
    assert not isinstance(dtstart, datetime)


@patch("src.utils.ical.get_coordinates")
def test_custom_timezone_respected(mock_coords, tmp_path):
    mock_coords.return_value = None

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location,name,description,timezone\n"
        "01.07.2025,12:00,1h,Tokyo,Conference,Details,Asia/Tokyo\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Events")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    dtstart = event.get("DTSTART").dt
    assert "Asia/Tokyo" in str(dtstart.tzinfo)


@patch("src.utils.ical.get_coordinates")
def test_event_summary_and_description(mock_coords, tmp_path):
    mock_coords.return_value = None

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "date,time,duration,location,name,description\n"
        "20.08.2025,10:00,2h,Room A,My Test Event,This is the description\n"
    )

    ical_bytes = csv_to_ical(csv_file, "Cal")
    cal = Calendar.from_ical(ical_bytes)
    event = cal.walk("VEVENT")[0]

    assert str(event.get("SUMMARY")) == "My Test Event"
    assert str(event.get("DESCRIPTION")) == "This is the description"


@patch("src.utils.ical.get_coordinates")
def test_empty_csv_produces_no_events(mock_coords, tmp_path):
    mock_coords.return_value = None

    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("date,time,duration,location,name,description\n")

    ical_bytes = csv_to_ical(csv_file, "Empty Cal")
    cal = Calendar.from_ical(ical_bytes)
    events = cal.walk("VEVENT")
    assert len(events) == 0
