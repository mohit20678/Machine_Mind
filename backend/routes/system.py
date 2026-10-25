"""Health check, dashboard numbers and model status."""
from fastapi import APIRouter, Depends, HTTPException

from backend.schemas.api import HealthOut, ModelStatus, StatsOut
from database import models
from database.db import connect
from ml_integration.predictor import get_predictor

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health():
    """Is the backend running and can it read the database?"""
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except Exception:
        raise HTTPException(status_code=503, detail="The database cannot be opened.")
    return {"status": "ok", "database": "ok"}


@router.get("/stats", response_model=StatsOut)
def stats():
    """Numbers for the dashboard cards."""
    return models.get_dashboard_stats()


@router.get("/model/status", response_model=ModelStatus)
def model_status(predictor=Depends(get_predictor)):
    """Tells the frontend whether real ML inference is connected or only the placeholder."""
    return predictor.status()
