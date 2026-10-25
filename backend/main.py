"""MachineMind backend (FastAPI).

Run from the project root:
    uvicorn backend.main:app --reload --port 8000

Interactive documentation (try every endpoint in the browser):
    http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.routes import alerts, analyses, machines, system
from backend.services.analysis_service import PredictionFailedError
from backend.services.audio_utils import AudioValidationError
from database import models
from database.db import init_db

logger = logging.getLogger("machinemind")


@asynccontextmanager
async def lifespan(app):
    init_db()  # create the database file and any missing tables when the backend starts
    yield


app = FastAPI(
    title="MachineMind API",
    description="Upload machine-sound recordings, analyse them and read the saved history.",
    version="0.6.0",
    lifespan=lifespan,
)

app.include_router(system.router)
app.include_router(machines.router)
app.include_router(analyses.router)
app.include_router(alerts.router)


def _error(status_code, message):
    """Every error leaves the backend in the same shape: {"detail": "message"}."""
    return JSONResponse(status_code=status_code, content={"detail": message})


@app.exception_handler(models.InvalidDataError)
async def invalid_data_handler(request: Request, error: models.InvalidDataError):
    return _error(422, str(error))


@app.exception_handler(AudioValidationError)
async def audio_error_handler(request: Request, error: AudioValidationError):
    return _error(422, str(error))


@app.exception_handler(models.NotFoundError)
async def not_found_handler(request: Request, error: models.NotFoundError):
    return _error(404, str(error))


@app.exception_handler(models.DuplicateError)
async def duplicate_handler(request: Request, error: models.DuplicateError):
    return _error(409, str(error))


@app.exception_handler(models.InUseError)
async def in_use_handler(request: Request, error: models.InUseError):
    return _error(409, str(error))


@app.exception_handler(PredictionFailedError)
async def prediction_failed_handler(request: Request, error: PredictionFailedError):
    return _error(503, str(error))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, error: RequestValidationError):
    parts = []
    for item in error.errors():
        where = [str(p) for p in item.get("loc", []) if p not in ("body", "query", "form", "path")]
        parts.append(f"{'.'.join(where) or 'request'}: {item.get('msg')}")
    return _error(422, "; ".join(parts) or "The request is not valid.")


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception):
    logger.exception("Unexpected error while handling %s", request.url.path)
    return _error(500, "Something went wrong inside the backend.")
