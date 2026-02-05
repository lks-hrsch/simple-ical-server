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


def csv_to_ical(csv_path: Path, calendar_name: str) -> bytes:
    cal = Calendar()
    cal.add("prodid", f"-//{settings.project_name}//mxm.dk//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", calendar_name)

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            entry = CSVEntry(**row)

            event = Event()
            event.add("summary", entry.name)
            event.add("description", entry.description)
            event.add("dtstamp", datetime.now(pytz.utc))

            # Unique UID based on name and date
            uid_seed = f"{entry.name}-{entry.date_str}-{entry.time_str}-{calendar_name}"
            uid = f"{hashlib.md5(uid_seed.encode()).hexdigest()}@{settings.project_name}"
            event.add("uid", uid)

            # Format location: Name\nStreet, Zip City, Country
            full_address = format_address(entry.location, entry.place)
            venue_name = entry.location_name or entry.name

            if full_address:
                event.add("location", f"{venue_name}\n{full_address}")
            else:
                event.add("location", venue_name)

            # Add Geocoding information only if we have an address
            if entry.location:
                coords = get_coordinates(full_address)
                if coords:
                    lat, lon = coords
                    event.add("geo", (lat, lon))
                    # Apple-specific structured location
                    apple_loc = f"geo:{lat},{lon}"
                    event.add(
                        "X-APPLE-STRUCTURED-LOCATION",
                        apple_loc,
                        parameters={
                            "VALUE": "URI",
                            "X-ADDRESS": full_address,
                            "X-TITLE": venue_name,
                            "X-APPLE-RADIUS": "70",
                        },
                    )

            # Check for all-day events (e.g., 1d, 5d)
            is_all_day = entry.duration.endswith("d")

            duration = parse_duration(entry.duration)
            start_dt = datetime.strptime(f"{entry.date_str} {entry.time_str}", "%d.%m.%Y %H:%M")
            tz = pytz.timezone(entry.timezone)
            start_dt = tz.localize(start_dt)

            if is_all_day:
                # For all-day events, DTSTART and DTEND should be dates (not datetimes)
                event.add("dtstart", start_dt.date())
                event.add("dtend", (start_dt + duration).date())
            else:
                event.add("dtstart", start_dt)
                event.add("dtend", start_dt + duration)

            cal.add_component(event)

    return cal.to_ical()
