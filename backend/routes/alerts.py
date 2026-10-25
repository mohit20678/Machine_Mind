"""Endpoints for reading alerts and marking them as reviewed."""
from fastapi import APIRouter

from backend.schemas.api import AlertOut
from database import models

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(machine_pk: int | None = None, only_new: bool = False, limit: int = 100):
    """Alerts, newest first. only_new=true hides alerts that were already reviewed."""
    return models.list_alerts(machine_pk=machine_pk, only_unacknowledged=only_new, limit=limit)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int):
    """Mark an alert as reviewed."""
    return models.acknowledge_alert(alert_id)
