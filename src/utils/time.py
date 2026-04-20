"""Utilities for parsing human-readable duration strings into ``timedelta`` objects.

Supported duration formats
--------------------------
- ``<N>min``  — N minutes  (e.g. ``"90min"``)
- ``<N>h``    — N hours    (e.g. ``"2h"``)
- ``<N>d``    — N days     (e.g. ``"3d"``, also signals an all-day event)
"""

from datetime import timedelta


def parse_duration(duration_str: str) -> timedelta:
    """Parse a duration string into a :class:`datetime.timedelta`.

    Recognised suffixes are ``min`` (minutes), ``h`` (hours), and ``d``
    (days).  The ``d`` suffix is also used as a sentinel by the iCal
    builder to detect all-day events.

    Args:
        duration_str: A duration string composed of an integer followed
            immediately by one of the supported unit suffixes.
            Examples: ``"30min"``, ``"1h"``, ``"5d"``.

    Returns:
        A :class:`~datetime.timedelta` representing the parsed duration.
        Returns ``timedelta(minutes=0)`` when the string does not match
        any known suffix, rather than raising an exception.

    Examples:
        >>> parse_duration("90min")
        datetime.timedelta(seconds=5400)
        >>> parse_duration("2h")
        datetime.timedelta(seconds=7200)
        >>> parse_duration("1d")
        datetime.timedelta(days=1)
    """
    if duration_str.endswith("min"):
        return timedelta(minutes=int(duration_str.replace("min", "")))
    elif duration_str.endswith("h"):
        return timedelta(hours=int(duration_str.replace("h", "")))
    elif duration_str.endswith("d"):
        return timedelta(days=int(duration_str.replace("d", "")))
    return timedelta(minutes=0)
