"""FastAPI application for MachineMind."""
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from database import models
from database.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs once when the server starts: make sure the database tables exist."""
    init_db()
    yield


app = FastAPI(
    title="MachineMind API",
    description="Backend for machine-sound anomaly detection.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    """Report that the backend is running."""
    return {"status": "ok"}


def _clean_row(row):
    """Prepare one database row for the JSON response."""
    row = dict(row)
    row["is_mock"] = bool(row["is_mock"])  # the database stores 0 or 1
    row.pop("stored_path", None)  # a server file path: users do not need it
    return row


@app.get("/history")
def get_history(
    machine_id: Optional[str] = None,
    prediction: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(100, ge=1, le=models.MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Return saved analyses, newest first, with optional filters."""
    try:
        machine_pk = None
        if machine_id is not None:
            machine = models.get_machine_by_code(machine_id)
            if machine is None:
                raise HTTPException(
                    status_code=404, detail=f"Machine '{machine_id}' does not exist."
                )
            machine_pk = machine["id"]

        filters = {
            "machine_pk": machine_pk,
            "prediction_label": prediction,
            "date_from": date_from,
            "date_to": date_to,
        }
        rows = models.list_analyses(**filters, limit=limit, offset=offset)
        total = models.count_analyses(**filters)
    except models.InvalidDataError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    except models.DatabaseError:
        raise HTTPException(
            status_code=500, detail="The history could not be read from the database."
        ) from None

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_clean_row(row) for row in rows],
    }
