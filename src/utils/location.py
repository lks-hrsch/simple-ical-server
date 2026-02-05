import re
from functools import lru_cache

from geopy.geocoders import Nominatim

from src.settings import settings


@lru_cache(maxsize=128)
def get_coordinates(address: str) -> tuple[float, float] | None:
    if not settings.geocode_enabled:
        return None

    geocoder = Nominatim(user_agent=settings.user_agent)
    try:
        location = geocoder.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except Exception:
        pass
    return None


def format_address(address: str, place: str = "") -> str:
    """Formats an address string, ensuring a comma before ZIP codes and appending place."""
    # Heuristic: Insert comma before 5-digit ZIP code if missing
    if address and "," not in address:
        address = re.sub(r"^(.*?)\s+(\d{5})\s+(.*)$", r"\1, \2 \3", address)

    if address and place:
        return f"{address}, {place}"
    return address or place
