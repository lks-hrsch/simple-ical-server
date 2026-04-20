from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.settings import settings


@pytest.fixture(autouse=True)
def mock_data_dir(monkeypatch):
    """Override DATA_DIR in settings to use test data."""
    test_data_path = Path(__file__).parent.parent / "data"
    monkeypatch.setattr(settings, "data_dir", test_data_path)


client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz():
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_list_calendars():
    response = client.get("/")
    assert response.status_code == 200
    assert "calendars" in response.json()
    assert "birthdays" in response.json()["calendars"]
    assert "allday" in response.json()["calendars"]


def test_get_calendar_ics():
    response = client.get("/birthdays.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "Emma Müller" in response.text
    # Verify timezone info (Europe/Berlin should be present or represented)
    assert "TZID:Europe/Berlin" in response.text or "TZID=Europe/Berlin" in response.text


def test_get_calendar_ics_allday():
    response = client.get("/allday.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "Holiday" in response.text
    # Verify all-day event format (DTSTART;VALUE=DATE:20240512)
    assert "DTSTART;VALUE=DATE:20240512" in response.text
    assert "DTEND;VALUE=DATE:20240513" in response.text
    assert "Vacation" in response.text
    assert "DTSTART;VALUE=DATE:20240513" in response.text
    assert "DTEND;VALUE=DATE:20240515" in response.text
    assert "Long Event" in response.text
    assert "DTSTART;VALUE=DATE:20240514" in response.text
    assert "DTEND;VALUE=DATE:20240519" in response.text


def test_get_calendar_not_found():
    response = client.get("/nonexistent.ics")
    assert response.status_code == 404


def test_list_calendars_missing_data_dir(monkeypatch, tmp_path):
    """When data_dir does not exist, should return empty list."""
    missing_dir = tmp_path / "nonexistent"
    monkeypatch.setattr(settings, "data_dir", missing_dir)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"calendars": []}


def test_get_calendar_500_on_corrupt_csv(monkeypatch, tmp_path):
    """get_calendar should return 500 when csv_to_ical raises."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    # Write a file that will cause a parse error (bad date format)
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        "date,time,duration,location,name,description\n"
        "not-a-date,nottime,1h,Somewhere,Bad Event,Desc\n"
    )
    response = client.get("/bad.ics")
    assert response.status_code == 500


def test_list_calendars_empty_data_dir(monkeypatch, tmp_path):
    """When data_dir exists but has no CSV files, should return empty list."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"calendars": []}


def test_get_calendar_content_type_is_text_calendar():
    """Verify Content-Type header is exactly text/calendar."""
    response = client.get("/birthdays.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")


def test_get_calendar_ics_contains_vcalendar_wrapper():
    response = client.get("/birthdays.ics")
    assert response.text.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in response.text


def test_get_calendar_ics_uid_present():
    """Each VEVENT in the calendar should have a UID."""
    from icalendar import Calendar

    response = client.get("/birthdays.ics")
    cal = Calendar.from_ical(response.content)
    events = cal.walk("VEVENT")
    assert len(events) > 0
    for event in events:
        assert event.get("UID") is not None


def test_get_calendar_not_found_detail():
    response = client.get("/nonexistent.ics")
    assert response.json()["detail"] == "Calendar not found"
