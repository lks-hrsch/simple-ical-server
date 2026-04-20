"""Core iCal generation logic: converts a CSV calendar file to iCal bytes.

The public API of this module is the single function :func:`csv_to_ical`.
It reads a CSV file row-by-row, validates each row against the
:class:`~src.models.CSVEntry` schema, builds a ``VEVENT`` component for
every entry, and assembles them into a ``VCALENDAR`` payload.
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path

import pytz
from icalendar import Calendar, Event

from src.models import CSVEntry
from src.settings import settings
from src.utils.location import format_address, get_coordinates
from src.utils.time import parse_duration


def _make_uid(name: str, date_str: str, time_str: str, calendar_name: str) -> str:
    """Build a stable, deterministic UID for a calendar event.

    The UID is an MD5 hex digest of the event identity fields, qualified
    with the project name so it is globally unique across calendars.

    Args:
        name: Event summary / title.
        date_str: Event date string (``DD.MM.YYYY``).
        time_str: Event start time string (``HH:MM``).
        calendar_name: Name of the containing calendar.

    Returns:
        A string of the form ``<md5hex>@<project_name>``.
    """
    seed = f"{name}-{date_str}-{time_str}-{calendar_name}"
    return f"{hashlib.md5(seed.encode()).hexdigest()}@{settings.project_name}"


async def _add_location_properties(event: Event, entry: CSVEntry) -> None:
    """Populate location-related iCal properties on *event* from *entry*.

    Sets the ``LOCATION`` property and, when geocoding succeeds, also
    adds ``GEO`` and ``X-APPLE-STRUCTURED-LOCATION``.

    Args:
        event: The ``VEVENT`` component to mutate.
        entry: The parsed CSV row providing address and venue data.
    """
    full_address = format_address(entry.location, entry.place)
    venue_name = entry.location_name or entry.name

    if full_address:
        event.add("location", f"{venue_name}\n{full_address}")
    else:
        event.add("location", venue_name)

    if not entry.location:
        return

    coords = await get_coordinates(full_address)
    if not coords:
        return

    lat, lon = coords
    event.add("geo", (lat, lon))
    event.add(
        "X-APPLE-STRUCTURED-LOCATION",
        f"geo:{lat},{lon}",
        parameters={
            "VALUE": "URI",
            "X-ADDRESS": full_address,
            "X-TITLE": venue_name,
            "X-APPLE-RADIUS": "70",
        },
    )


def _add_time_properties(event: Event, entry: CSVEntry) -> None:
    """Populate ``DTSTART`` and ``DTEND`` on *event* from *entry*.

    Handles both timed events (timezone-aware ``datetime`` values) and
    all-day events (plain ``date`` values), determined by whether the
    duration string ends with ``"d"``.

    Args:
        event: The ``VEVENT`` component to mutate.
        entry: The parsed CSV row providing date, time, duration, and
            timezone data.
    """
    is_all_day = entry.duration.endswith("d")
    duration = parse_duration(entry.duration)
    tz = pytz.timezone(entry.timezone)
    start_dt = tz.localize(datetime.strptime(f"{entry.date_str} {entry.time_str}", "%d.%m.%Y %H:%M"))

    if is_all_day:
        event.add("dtstart", start_dt.date())
        event.add("dtend", (start_dt + duration).date())
    else:
        event.add("dtstart", start_dt)
        event.add("dtend", start_dt + duration)


async def _build_event(entry: CSVEntry, calendar_name: str) -> Event:
    """Construct a single ``VEVENT`` component from a parsed CSV row.

    Args:
        entry: Validated CSV row data.
        calendar_name: Name of the containing calendar, used for UID
            generation.

    Returns:
        A fully populated :class:`icalendar.Event` component.
    """
    event = Event()
    event.add("summary", entry.name)
    event.add("description", entry.description)
    event.add("dtstamp", datetime.now(pytz.utc))
    event.add("uid", _make_uid(entry.name, entry.date_str, entry.time_str, calendar_name))

    await _add_location_properties(event, entry)
    _add_time_properties(event, entry)

    return event


async def csv_to_ical(csv_path: Path, calendar_name: str) -> bytes:
    """Convert a CSV calendar file into an iCal-formatted byte string.

    Each row in the CSV file is mapped to a ``VEVENT`` component inside a
    single ``VCALENDAR`` object.  The function handles both timed events
    and all-day events (detected by a ``d`` suffix in the ``duration``
    column), optional venue geocoding, and Apple-specific structured
    location metadata.

    Stable ``UID`` values are generated deterministically from the event
    name, date, time, and calendar name so that re-generating the same
    calendar produces the same UIDs.  This allows calendar clients to
    update existing events rather than creating duplicates.

    Args:
        csv_path: Path to the ``.csv`` file to read.  The file must be
            UTF-8 encoded and have a header row whose column names match
            the field aliases defined on :class:`~src.models.CSVEntry`
            (``date``, ``time``, ``duration``, ``location``,
            ``location_name``, ``place``, ``name``, ``description``,
            ``timezone``).
        calendar_name: Display name embedded in the ``X-WR-CALNAME``
            iCal property.  Also incorporated into event UIDs to keep
            them unique across calendars.

    Returns:
        The complete iCal payload as a raw ``bytes`` object, ready to be
        sent as a ``text/calendar`` HTTP response.

    Raises:
        FileNotFoundError: If ``csv_path`` does not point to an existing
            file (propagated from :func:`open`).
        pydantic.ValidationError: If a CSV row fails schema validation
            (missing required columns, wrong types, etc.).
        Exception: Any other error from CSV parsing, timezone lookup, or
            iCal serialisation is propagated to the caller.
    """
    cal = Calendar()
    cal.add("prodid", f"-//{settings.project_name}//mxm.dk//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", calendar_name)

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            entry = CSVEntry(**row)
            cal.add_component(await _build_event(entry, calendar_name))

    return cal.to_ical()
