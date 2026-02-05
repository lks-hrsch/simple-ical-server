from pydantic import BaseModel, Field, ConfigDict
from datetime import date, time

class CSVEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_str: str = Field(alias="date")
    time_str: str = Field(alias="time")
    duration: str
    location: str
    name: str
    description: str
    timezone: str = "Europe/Berlin"  # Default timezone
