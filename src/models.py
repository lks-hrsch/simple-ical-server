from pydantic import BaseModel, ConfigDict, Field

from src.settings import settings


class CSVEntry(BaseModel):
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
