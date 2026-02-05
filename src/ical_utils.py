import csv
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from icalendar import Calendar, Event

from src.models import CSVEntry


def parse_duration(duration_str: str) -> timedelta:
    """Parses a duration string like '30min', '1h', '1d' into a timedelta."""
    if duration_str.endswith("min"):
        return timedelta(minutes=int(duration_str.replace("min", "")))
    elif duration_str.endswith("h"):
        return timedelta(hours=int(duration_str.replace("h", "")))
    elif duration_str.endswith("d"):
        return timedelta(days=int(duration_str.replace("d", "")))
    return timedelta(minutes=0)


def csv_to_ical(csv_path: Path, calendar_name: str) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Simple iCal Server//mxm.dk//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", calendar_name)

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            entry = CSVEntry(**row)

            event = Event()
            event.add("summary", entry.name)
            event.add("description", entry.description)
            event.add("location", entry.location)

            # Check for all-day events (e.g., 1d, 5d)
            is_all_day = entry.duration.endswith("d")

            if is_all_day:
                # For all-day events, ignore time and use date objects
                dt_start = datetime.strptime(entry.date_str, "%d.%m.%Y").date()
                try:
                    num_days = int(entry.duration.replace("d", ""))
                except ValueError:
                    num_days = 1  # Fallback to 1 day if parsing fails
                dt_end = dt_start + timedelta(days=num_days)
            else:
                # Parse date and time with timezone awareness
                tz = pytz.timezone(entry.timezone)
                naive_start = datetime.strptime(f"{entry.date_str} {entry.time_str}", "%d.%m.%Y %H:%M")
                dt_start = tz.localize(naive_start)
                duration = parse_duration(entry.duration)
                dt_end = dt_start + duration

            event.add("dtstart", dt_start)
            event.add("dtend", dt_end)
            cal.add_component(event)

    return cal.to_ical()
