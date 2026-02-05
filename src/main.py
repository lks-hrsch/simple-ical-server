from fastapi import FastAPI

from src.routes import router

app = FastAPI(title="Simple iCal Server")

app.include_router(router)
