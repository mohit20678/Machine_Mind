"""The ONE place where the frontend gets its data.

Milestone 5 (now): reads the SQLite database directly. This is a temporary shortcut.
Milestone 6: the functions below will call the FastAPI backend instead.
The pages will not need to change, because they only use the functions in this file.
"""
import sys
from datetime import datetime
from pathlib import Path

# Let the frontend import the "database" package that sits in the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from database import models  # noqa: E402
from database.db import init_db  # noqa: E402

# Pages catch this to show a friendly message.
DatabaseError = models.DatabaseError

MACHINE_TYPES = ["Pump", "Fan", "Slider", "Valve", "Motor", "Gearbox", "Other"]

MACHINE_COLUMNS = ["machine_id", "name", "machine_type", "location", "analysis_count", "created_at"]
ANALYSIS_COLUMNS = ["timestamp", "machine_id", "filename", "prediction", "anomaly_score", "source"]
ALERT_COLUMNS = ["timestamp", "machine_id", "filename", "anomaly_score", "message", "status"]


def _to_local_time(series):
    """Turn stored UTC time text into your computer's local time."""
    local_zone = datetime.now().astimezone().tzinfo
    return pd.to_datetime(series, utc=True).dt.tz_convert(local_zone).dt.tz_localize(None)


def load_stats():
    """Counts for the dashboard cards (a dictionary of numbers)."""
    init_db()
    return models.get_dashboard_stats()


def load_machines_df():
    """Registered machines as a table. Empty table if there are none."""
    init_db()
    frame = pd.DataFrame(models.list_machines(), columns=MACHINE_COLUMNS)
    frame["created_at"] = _to_local_time(frame["created_at"])
    return frame


def load_analyses_df(limit=1000):
    """Saved analyses (newest first) as a table. Empty table if there are none."""
    init_db()
    rows = models.list_analyses(limit=limit)
    records = [
        {
            "timestamp": row["created_at"],
            "machine_id": row["machine_code"],
            "filename": row["filename"],
            "prediction": row["prediction_label"],
            "anomaly_score": row["anomaly_score"],
            "source": "MOCK (not a real model)" if row["is_mock"] else "Real model",
        }
        for row in rows
    ]
    frame = pd.DataFrame(records, columns=ANALYSIS_COLUMNS)
    frame["timestamp"] = _to_local_time(frame["timestamp"])
    return frame


def load_alerts_df(limit=1000):
    """Saved alerts (newest first) as a table. Empty table if there are none."""
    init_db()
    rows = models.list_alerts(limit=limit)
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
    """Save a new machine. Raises DatabaseError with a clear message if it is not accepted."""
    init_db()
    return models.create_machine(machine_id, name, machine_type, location)
