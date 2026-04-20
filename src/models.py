"""Pydantic data models for parsing CSV calendar entries.

This module defines the schema used to validate and parse rows read from
the CSV data files that back each calendar served by the application.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.settings import settings


class CSVEntry(BaseModel):
    """Represents a single event row parsed from a CSV calendar file.

    Fields map directly to the column headers in the CSV, with a few
    aliases to match the header names used on disk (e.g. ``date`` ->
    ``date_str``).  Default values for ``place`` and ``timezone`` are
    pulled from application settings so that CSV files do not need to
    repeat them on every row.

    Attributes:
        date_str: Event date as a string in ``DD.MM.YYYY`` format
            (CSV column header: ``date``).
        time_str: Event start time as a string in ``HH:MM`` 24-hour
            format (CSV column header: ``time``).
        duration: Duration string using one of the supported suffixes:
            ``min`` (minutes), ``h`` (hours), or ``d`` (all-day days).
            Example values: ``"90min"``, ``"2h"``, ``"3d"``.
        location_name: Optional human-readable venue name shown in the
            calendar event.  Defaults to the event ``name`` when empty.
        location: Street address of the venue (e.g.
            ``"Musterstraße 1 12345 Berlin"``).  May be an empty string
            for events without a fixed location.
        place: Country or region appended to the address for geocoding
            and display purposes.  Defaults to ``settings.default_place``.
        name: Title / summary of the event.
        description: Free-text description of the event shown in the
            calendar body.
        timezone: IANA timezone name used to localise the event start
            time.  Defaults to ``settings.tz``.
    """

    model_config = ConfigDict(populate_by_name=True)

    date_str: str = Field(alias="date")
    time_str: str = Field(alias="time")
    duration: str
    location_name: str = ""
    location: str
    place: str = Field(default_factory=lambda: settings.default_place)
    name: str
    description: str
    timezone: str = Field(default_factory=lambda: settings.tz)
