from pydantic import BaseModel, ConfigDict, Field

from src.settings import settings


class CSVEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_str: str = Field(alias="date")
    time_str: str = Field(alias="time")
    duration: str
    location: str
    name: str
    description: str
    timezone: str = Field(default_factory=lambda: settings.tz)
