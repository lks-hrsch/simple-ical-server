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
