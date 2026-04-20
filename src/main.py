"""Entry point for the simple-ical-server FastAPI application.

This module creates the FastAPI application instance and registers the API
router that handles calendar listing and iCal file serving.
"""

from fastapi import FastAPI

from src.routes import router

app = FastAPI(title="Simple iCal Server")

app.include_router(router)
