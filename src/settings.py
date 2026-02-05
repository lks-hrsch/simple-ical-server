import tomllib
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_metadata() -> tuple[str, str]:
    """Reads the name and version from pyproject.toml."""
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["name"], data["project"]["version"]
    except Exception:
        return "simple-ical-server", "0.1.0"


_name, _version = get_project_metadata()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = _name
    tz: str = "Europe/Berlin"
    data_dir: Path = Path("data")
    default_place: str = "Germany"
    geocode_enabled: bool = True
    user_agent: str = f"{_name}/{_version}"


settings = Settings()
