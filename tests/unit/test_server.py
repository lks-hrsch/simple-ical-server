from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

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
    bad_csv.write_text("date,time,duration,location,name,description\nnot-a-date,nottime,1h,Somewhere,Bad Event,Desc\n")
    response = client.get("/bad.ics")
    assert response.status_code == 500


def test_list_calendars_empty_data_dir(monkeypatch, tmp_path):
    """When data_dir exists but has no CSV files, should return empty list."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"calendars": []}


def test_get_calendar_content_type_is_text_calendar():
    """Verify Content-Type header starts with text/calendar (charset may be appended by FastAPI)."""
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
    assert response.status_code == 404
    assert response.json()["detail"] == "Calendar not found"


# ---------------------------------------------------------------------------
# Path-traversal protection
# ---------------------------------------------------------------------------


def test_path_traversal_dot_dot_substring_is_safe(monkeypatch, tmp_path):
    """Names containing '..' as a *substring* (e.g. '..secret') are safe.

    'f"{name}.csv"' constructs '..secret.csv', which resolves *inside*
    data_dir — no traversal possible without a path separator.  The
    resolve() guard is the real security boundary; the string check only
    rejects explicit separator characters ('/' and '\\').
    """
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    response = client.get("/..secret.ics")
    # No '/' or '\\' in name → passes string check.  Resolves inside
    # data_dir → passes resolve() check.  File doesn't exist → 404.
    assert response.status_code == 404


def test_path_traversal_only_dot_dot():
    """A URL of '/../.ics' is normalised/rejected at the routing layer."""
    response = client.get("/../.ics")
    # httpx normalises '/../.ics' → '/.ics'; empty-name segment doesn't
    # match /{name}.ics, so the router returns 404.  Either way no file
    # is served — both 400 and 404 are acceptable safe responses.
    assert response.status_code in (400, 404)


def test_path_traversal_forward_slash_not_routed():
    """URLs with literal '/' in the name won't match /{name}.ics at all → 404.
    This is safe: the router never reaches get_calendar, so no file is served."""
    response = client.get("/sub/dir.ics")
    assert response.status_code == 404  # router doesn't match multi-segment paths


def test_path_traversal_forward_slash_urlencoded():
    """Starlette decodes %2F before routing, so encoded slashes also never reach the handler.
    Both literal and percent-encoded slashes yield 404 — safe, no data is leaked."""
    response = client.get("/sub%2Fdir.ics")
    assert response.status_code == 404  # router decodes %2F → multi-segment → no match


def test_path_traversal_backslash():
    """Names containing '\\' must be rejected with 400 (Windows path-separator defence)."""
    response = client.get("/back%5Cslash.ics")
    assert response.status_code == 400


def test_path_traversal_safe_name_stays_404(monkeypatch, tmp_path):
    """A clean name that resolves inside data_dir but has no CSV returns 404, not 400."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    response = client.get("/safe_name.ics")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Hypothesis fuzz test
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=500)
@given(name=st.text(min_size=0, max_size=100))
def test_path_traversal_fuzz(name):
    """Any calendar name must yield 200, 400, or 404 — never 500 from the validation layer."""
    response = client.get(f"/{quote(name, safe='')}.ics")
    assert response.status_code in (200, 400, 404)
    # Only '/' and '\\' are explicitly blocked with 400.
    # '/' in the URL creates multiple path segments so the router returns 404
    # before get_calendar runs — both outcomes are safe (no file served).
    # '..' as a substring (no separator) is NOT blocked; the resolve() check
    # inside the handler is the real security boundary.
    if ("/" not in name) and ("\\" in name):
        assert response.status_code == 400
