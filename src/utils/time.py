from datetime import timedelta


def parse_duration(duration_str: str) -> timedelta:
    """Parses a duration string like '30min', '1h', '1d' into a timedelta."""
    if duration_str.endswith("min"):
        return timedelta(minutes=int(duration_str.replace("min", "")))
    elif duration_str.endswith("h"):
        return timedelta(hours=int(duration_str.replace("h", "")))
    elif duration_str.endswith("d"):
        return timedelta(days=int(duration_str.replace("d", "")))
    return timedelta(minutes=0)
