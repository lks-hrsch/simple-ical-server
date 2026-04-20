"""FastAPI route definitions for the simple-ical-server API.

Endpoints
---------
GET /
    Returns a JSON object with a single key ``"calendars"`` whose value
    is a list of calendar name strings derived from the ``.csv`` files
    present in the configured data directory.

GET /{name}.ics
    Generates and returns an iCal (``.ics``) file for the calendar whose
    CSV data file is named ``{name}.csv``.

GET /healthz
    Kubernetes-style liveness probe — always returns ``{"status": "ok"}``.

GET /readyz
    Kubernetes-style readiness probe — always returns
    ``{"status": "ready"}``.
"""

from fastapi import APIRouter, HTTPException, Response

from src.settings import settings
from src.utils.ical import csv_to_ical

router = APIRouter()


@router.get("/")
async def list_calendars():
    """List all available calendar names.

    Scans the configured data directory for files with a ``.csv``
    extension and returns their base names (without the extension).

    Returns:
        A JSON object with a single key ``"calendars"`` whose value is
        a list of calendar name strings.  Returns an empty list when
        the data directory does not exist yet.

    Example response::

        {"calendars": ["events", "workshops"]}
    """
    if not settings.data_dir.exists():
        return {"calendars": []}

    calendars = [f.stem for f in settings.data_dir.glob("*.csv")]
    return {"calendars": calendars}


@router.get("/{name}.ics")
async def get_calendar(name: str):
    """Generate and serve an iCal file for the named calendar.

    Reads the CSV file at ``{data_dir}/{name}.csv``, converts every row
    to an iCal ``VEVENT`` component, and returns the full ``VCALENDAR``
    payload as a ``text/calendar`` response body.

    Args:
        name: The calendar identifier, which must correspond to a file
            named ``{name}.csv`` inside the configured data directory.

    Returns:
        An HTTP response with ``Content-Type: text/calendar`` and the
        raw iCal bytes as the body.

    Raises:
        HTTPException: 404 when no CSV file with the given name exists.
        HTTPException: 500 when the CSV file exists but cannot be parsed
            or converted (the detail field contains the underlying error
            message).
    """
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
    """Liveness check.

    Returns:
        ``{"status": "ok"}`` unconditionally.  A successful HTTP 200
        response indicates the process is alive and the event loop is
        running.
    """
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Readiness check.

    Returns:
        ``{"status": "ready"}`` unconditionally.  Extend this handler
        if readiness should depend on external dependencies (e.g.
        confirming the data directory is mounted and readable).
    """
    return {"status": "ready"}
