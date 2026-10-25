"""The ONE place where the frontend talks to the backend.

Milestone 6: every function here calls the FastAPI backend over HTTP.
The frontend no longer reads the database directly.

The backend address can be changed with the environment variable MACHINEMIND_API_URL
(default http://127.0.0.1:8000).
"""
import os
from datetime import datetime

import pandas as pd
import requests

API_URL = os.environ.get("MACHINEMIND_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 15      # seconds, for normal requests
ANALYSIS_TIMEOUT = 120    # seconds, an analysis may take longer

MACHINE_TYPES = ["Pump", "Fan", "Slider", "Valve", "Motor", "Gearbox", "Other"]

MACHINE_COLUMNS = ["machine_id", "name", "machine_type", "location", "analysis_count", "created_at"]
ANALYSIS_COLUMNS = ["timestamp", "machine_id", "filename", "prediction", "anomaly_score", "source"]
ALERT_COLUMNS = ["timestamp", "machine_id", "filename", "anomaly_score", "message", "status"]


class BackendError(Exception):
    """The backend refused the request or failed. The message can be shown to the user."""


class BackendUnavailable(BackendError):
    """The backend is not running or cannot be reached."""


def _request(method, path, timeout=REQUEST_TIMEOUT, **kwargs):
    """Call the backend and return its JSON answer (None for an empty answer)."""
    try:
        response = requests.request(method, API_URL + path, timeout=timeout, **kwargs)
    except requests.exceptions.ConnectionError:
        raise BackendUnavailable(
            f"The backend is not running at {API_URL}. Start it in a second terminal with: "
            "uvicorn backend.main:app --reload --port 8000"
        ) from None
    except requests.exceptions.Timeout:
        raise BackendError("The backend took too long to answer. Please try again.") from None
    except requests.exceptions.RequestException as error:
        raise BackendError(f"The backend could not be reached: {error}") from None

    if response.status_code >= 400:
        detail = None
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail")
        except ValueError:
            pass
        raise BackendError(str(detail) if detail else f"The backend returned an error ({response.status_code}).")

    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        raise BackendError("The backend sent an answer that could not be understood.") from None


def _to_local_time(series):
    """Turn stored UTC time text into your computer's local time."""
    local_zone = datetime.now().astimezone().tzinfo
    return pd.to_datetime(series, utc=True).dt.tz_convert(local_zone).dt.tz_localize(None)


def check_backend():
    """Raises BackendError if the backend or its database is not working."""
    _request("GET", "/api/health")


def get_model_status():
    """Is real ML inference connected, or only the placeholder?"""
    return _request("GET", "/api/model/status")


def load_stats():
    return _request("GET", "/api/stats")


def list_machines():
    """Registered machines as a list of dictionaries."""
    return _request("GET", "/api/machines")


def load_machines_df():
    """Registered machines as a table. Empty table if there are none."""
    frame = pd.DataFrame(list_machines(), columns=MACHINE_COLUMNS)
    frame["created_at"] = _to_local_time(frame["created_at"])
    return frame


def load_analyses_df(limit=1000):
    """Saved analyses (newest first) as a table. Empty table if there are none."""
    page = _request("GET", "/api/analyses", params={"limit": limit})
    records = [
        {
            "timestamp": row["created_at"],
            "machine_id": row["machine_code"],
            "filename": row["filename"],
            "prediction": row["prediction_label"],
            "anomaly_score": row["anomaly_score"],
            "source": "MOCK (not a real model)" if row["is_mock"] else "Real model",
        }
        for row in page["items"]
    ]
    frame = pd.DataFrame(records, columns=ANALYSIS_COLUMNS)
    frame["timestamp"] = _to_local_time(frame["timestamp"])
    return frame


def load_alerts_df(limit=1000):
    """Saved alerts (newest first) as a table. Empty table if there are none."""
    rows = _request("GET", "/api/alerts", params={"limit": limit})
    records = [
        {
            "timestamp": row["created_at"],
            "machine_id": row["machine_code"],
            "filename": row["filename"],
            "anomaly_score": row["anomaly_score"],
            "message": row["message"],
            "status": "Reviewed" if row["acknowledged"] else "New",
        }
        for row in rows
    ]
    frame = pd.DataFrame(records, columns=ALERT_COLUMNS)
    frame["timestamp"] = _to_local_time(frame["timestamp"])
    return frame


def load_dashboard_data():
    """Everything the dashboard needs: (stats, machines, analyses, alerts)."""
    return load_stats(), load_machines_df(), load_analyses_df(), load_alerts_df()


def register_machine(machine_id, name, machine_type, location):
    """Save a new machine. Raises BackendError with a clear message if it is not accepted."""
    return _request(
        "POST",
        "/api/machines",
        json={
            "machine_id": machine_id,
            "name": name,
            "machine_type": machine_type,
            "location": location or None,
        },
    )


def analyse_recording(machine_pk, filename, file_bytes):
    """Send a recording to the backend for analysis. Returns the backend's result dictionary."""
    return _request(
        "POST",
        "/api/analyses",
        timeout=ANALYSIS_TIMEOUT,
        data={"machine_pk": str(machine_pk)},
        files={"file": (filename, file_bytes, "audio/wav")},
    )
