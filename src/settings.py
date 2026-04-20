"""Application settings loaded from environment variables and an optional .env file.

Settings are managed via ``pydantic-settings``.  Every field can be
overridden by the corresponding upper-cased environment variable (e.g.
``TZ``, ``DATA_DIR``, ``GEOCODE_ENABLED``).  An ``.env`` file in the
project root is also read automatically when present.
"""

import tomllib
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_metadata() -> tuple[str, str]:
    """Read the project name and version from ``pyproject.toml``.

    The values are used to populate default ``Settings`` fields (e.g.
    the ``user_agent`` string sent to the Nominatim geocoder and the
    ``prodid`` property written into generated iCal files).

    Returns:
        A two-element tuple ``(name, version)``.  If ``pyproject.toml``
        cannot be found or parsed the fallback values
        ``("simple-ical-server", "0.1.0")`` are returned instead.
    """
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["name"], data["project"]["version"]
    except Exception:
        return "simple-ical-server", "0.1.0"


_name, _version = get_project_metadata()


class Settings(BaseSettings):
    """Global application configuration.

    All fields can be overridden via environment variables or a ``.env``
    file.  Unknown environment variables are silently ignored
    (``extra="ignore"``).

    Attributes:
        project_name: Human-readable project identifier, sourced from
            ``pyproject.toml``.  Used in iCal ``PRODID`` and HTTP
            ``User-Agent`` headers.
        tz: Default IANA timezone applied to events that do not supply
            their own ``timezone`` column in the CSV.
            Example: ``"Europe/Berlin"``.
        data_dir: Filesystem path to the directory that contains the
            ``.csv`` calendar files.  Relative paths are resolved from
            the current working directory at runtime.
        default_place: Country or region appended to event addresses
            when the CSV row does not provide an explicit ``place``
            value.  Used for geocoding and display.
        geocode_enabled: When ``True`` (the default), the server calls
            the Nominatim geocoder to resolve latitude/longitude
            coordinates for each unique address and embeds them in the
            iCal output.  Set to ``False`` to disable all outbound
            geocoding requests (useful in offline or CI environments).
        user_agent: ``User-Agent`` string sent with Nominatim HTTP
            requests.  Nominatim's usage policy requires a descriptive,
            application-specific value.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = _name
    tz: str = "Europe/Berlin"
    data_dir: Path = Path("data")
    default_place: str = "Germany"
    geocode_enabled: bool = True
    user_agent: str = f"{_name}/{_version}"


settings = Settings()
