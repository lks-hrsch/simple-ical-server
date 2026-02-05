from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src import main
from src.main import app


@pytest.fixture(autouse=True)
def mock_data_dir(monkeypatch):
    """Override DATA_DIR to use test data."""
    test_data_path = Path(__file__).parent.parent / "data"
    monkeypatch.setattr(main, "DATA_DIR", test_data_path)


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


def test_get_calendar_ics():
    response = client.get("/birthdays.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR" in response.text
    assert "Emma Müller" in response.text
    # Verify timezone info (Europe/Berlin should be present or represented)
    assert "TZID:Europe/Berlin" in response.text or "TZID=Europe/Berlin" in response.text


def test_get_calendar_not_found():
    response = client.get("/nonexistent.ics")
    assert response.status_code == 404
