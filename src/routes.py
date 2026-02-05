from fastapi import APIRouter, HTTPException, Response

from src.settings import settings
from src.utils.ical import csv_to_ical

router = APIRouter()


@router.get("/")
async def list_calendars():
    """Lists all available calendars based on .csv files in the data directory."""
    if not settings.data_dir.exists():
        return {"calendars": []}

    calendars = [f.stem for f in settings.data_dir.glob("*.csv")]
    return {"calendars": calendars}


@router.get("/{name}.ics")
async def get_calendar(name: str):
    """Serves the iCal file for a given calendar name."""
    csv_path = settings.data_dir / f"{name}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Calendar not found")

    try:
        ical_content = csv_to_ical(csv_path, name)
        return Response(content=ical_content, media_type="text/calendar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/healthz")
async def healthz():
    """Liveness check."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Readiness check."""
    return {"status": "ready"}
