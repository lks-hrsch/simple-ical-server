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
    Kubernetes-style readiness probe — returns ``{"status": "ready"}``
    when ``data_dir`` exists, is a directory, and is readable; returns
    ``{"status": "not ready", "reason": "..."}`` with HTTP 503 otherwise.

.. note::
    ``GET /{name}.ics`` validates ``name`` against path-traversal
    sequences before constructing the file path.
"""

import os

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse

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
            Names containing ``/`` or ``\\`` are rejected immediately.
            A secondary ``resolve()`` check ensures the constructed path
            cannot escape ``data_dir`` even via symlinks or other
            filesystem tricks.

    Returns:
        An HTTP response with ``Content-Type: text/calendar`` and the
        raw iCal bytes as the body.

    Raises:
        HTTPException: 400 when ``name`` contains path separators or the
            resolved path would escape the configured data directory.
        HTTPException: 404 when no CSV file with the given name exists.
        HTTPException: 500 when the CSV file exists but cannot be parsed
            or converted (the detail field contains the underlying error
            message).
    """
    # Reject names containing path separators (the main traversal vector).
    # Note: ".." alone is safe here because f"{name}.csv" = "...csv", which
    # resolves inside data_dir.  The resolve() guard below handles symlinks
    # and any other filesystem-level escape attempts.
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid calendar name")

    csv_path = settings.data_dir / f"{name}.csv"

    # Defense in depth: resolved path must stay inside data_dir.
    # Catches symlink traversal and any OS-specific path quirks.
    try:
        resolved = csv_path.resolve()
        data_dir_resolved = settings.data_dir.resolve()
        resolved.relative_to(data_dir_resolved)
    except (ValueError, OSError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid calendar name")

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
    """Kubernetes readiness probe.

    Returns 200 when the application is ready to serve requests — specifically
    when ``data_dir`` exists, is a directory, and is readable.  Returns 503
    otherwise so that load-balancers and orchestrators can stop routing traffic
    until the data volume is available.
    """
    data_dir = settings.data_dir
    if not data_dir.exists():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "data_dir does not exist"},
        )
    if not data_dir.is_dir():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "data_dir is not a directory"},
        )
    if not os.access(data_dir, os.R_OK | os.X_OK):
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "data_dir is not readable"},
        )
    return {"status": "ready"}
