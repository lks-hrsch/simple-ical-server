"""Utilities for address formatting and geocoding via the Nominatim service.

Geocoding results are cached in-process using :func:`functools.lru_cache`
so that repeated lookups for the same address (common when many events
share a venue) do not generate redundant HTTP requests to Nominatim.

A module-level threading lock enforces Nominatim's one-request-per-second
policy even when multiple threads serve concurrent HTTP requests.  The
throttle is applied only on cache misses, so cached lookups are
unaffected.

Note:
    Nominatim's usage policy requires a meaningful ``User-Agent`` string
    and prohibits more than one request per second.  The ``user_agent``
    value is taken from :data:`src.settings.settings` so it can be
    configured via the ``USER_AGENT`` environment variable.
"""

import re
import threading
import time
from functools import lru_cache

from geopy.geocoders import Nominatim

from src.settings import settings

_geocode_lock = threading.Lock()
_MIN_GEOCODE_INTERVAL: float = 1.0  # seconds — Nominatim policy
# Initialise far enough in the past so the very first call never waits.
# time.monotonic()'s epoch is undefined, so we can't use 0.0 safely.
_last_geocode_time: float = -_MIN_GEOCODE_INTERVAL


def _throttle_geocode() -> None:
    """Block until at least 1 second has elapsed since the last Nominatim call.

    Uses a module-level lock so the invariant holds across threads.
    Must be called while *not* holding any other lock to avoid deadlocks.
    """
    global _last_geocode_time
    with _geocode_lock:
        now = time.monotonic()
        wait = _MIN_GEOCODE_INTERVAL - (now - _last_geocode_time)
        if wait > 0:
            time.sleep(wait)
        _last_geocode_time = time.monotonic()


@lru_cache(maxsize=128)
def get_coordinates(address: str) -> tuple[float, float] | None:
    """Return the latitude and longitude for an address string.

    Results are memoised with an LRU cache keyed on the exact address
    string, so identical addresses are only geocoded once per process
    lifetime.  Geocoding can be disabled globally by setting
    ``GEOCODE_ENABLED=false`` in the environment.

    The function calls :func:`_throttle_geocode` before each live
    Nominatim request to comply with the one-request-per-second policy.
    The throttle is bypassed entirely when geocoding is disabled or when
    the result is served from cache.

    Args:
        address: A full address string to geocode, e.g.
            ``"Musterstraße 1, 12345 Berlin, Germany"``.

    Returns:
        A ``(latitude, longitude)`` tuple of floats when the address is
        successfully resolved, or ``None`` if geocoding is disabled, the
        address could not be found, or any network/API error occurs.
    """
    if not settings.geocode_enabled:
        return None

    _throttle_geocode()
    geocoder = Nominatim(user_agent=settings.user_agent)
    try:
        location = geocoder.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except Exception:
        # Silently swallow geocoding errors so a single bad address does
        # not abort the entire calendar generation.
        pass
    return None


def format_address(address: str, place: str = "") -> str:
    """Format a raw address string for consistent display and geocoding.

    Applies two transformations:

    1. **ZIP-code comma insertion** — If the address contains no comma
       and matches the pattern ``<street> <5-digit-zip> <city>``, a
       comma is inserted before the ZIP code so the result looks like
       ``"Musterstraße 1, 12345 Berlin"``.
    2. **Place appending** — If a non-empty ``place`` string is given
       (e.g. ``"Germany"``), it is appended after a comma.

    Args:
        address: Raw street/location string from the CSV.  May be empty.
        place: Optional country or region suffix (e.g. ``"Germany"``).
            Defaults to an empty string.

    Returns:
        A formatted address string.  When ``address`` is empty and
        ``place`` is provided, only the ``place`` value is returned.
        When both are empty, an empty string is returned.

    Examples:
        >>> format_address("Musterstraße 1 12345 Berlin", "Germany")
        'Musterstraße 1, 12345 Berlin, Germany'
        >>> format_address("Musterstraße 1, 12345 Berlin")
        'Musterstraße 1, 12345 Berlin'
        >>> format_address("", "Germany")
        'Germany'
    """
    # Heuristic: Insert comma before 5-digit ZIP code if missing.
    # This handles German addresses written without punctuation in the CSV.
    if address and "," not in address:
        address = re.sub(r"^(.*?)\s+(\d{5})\s+(.*)$", r"\1, \2 \3", address)

    if address and place:
        return f"{address}, {place}"
    return address or place
