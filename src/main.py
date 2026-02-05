from pathlib import Path

from fastapi import FastAPI, HTTPException, Response

from src.ical_utils import csv_to_ical

app = FastAPI(title="Simple iCal Server")

DATA_DIR = Path("data")


@app.get("/")
async def list_calendars():
    """Lists all available calendars based on .csv files in the data directory."""
    if not DATA_DIR.exists():
        return {"calendars": []}

    calendars = [f.stem for f in DATA_DIR.glob("*.csv")]
    return {"calendars": calendars}


@app.get("/{name}.ics")
async def get_calendar(name: str):
    """Serves the iCal file for a given calendar name."""
    csv_path = DATA_DIR / f"{name}.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Calendar not found")

    try:
        ical_content = csv_to_ical(csv_path, name)
        return Response(content=ical_content, media_type="text/calendar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/healthz")
async def healthz():
    """Liveness check."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness check."""
    return {"status": "ready"}
