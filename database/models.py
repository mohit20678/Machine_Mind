"""Database access functions (create, read, update, delete) for MachineMind.

Every function takes an optional db_path so tests can use a temporary database.
All values are passed to SQL with ? placeholders (parameterized queries), so text
typed by a user can never change the meaning of a query.
"""
import math
import re
import sqlite3
from datetime import date, datetime

from database.db import connect, utc_now

PREDICTION_LABELS = ("Normal", "Potentially Abnormal")
MACHINE_CODE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,49}")
MAX_PAGE_SIZE = 1000


class DatabaseError(Exception):
    """Base class for our errors. The messages are written to be shown to users."""


class InvalidDataError(DatabaseError):
    """The data given was missing or not acceptable."""


class DuplicateError(DatabaseError):
    """A record with the same unique value already exists."""


class NotFoundError(DatabaseError):
    """The requested record does not exist."""


class InUseError(DatabaseError):
    """The record cannot be removed because other records depend on it."""


# ---------------------------------------------------------------- checking input

def _clean_text(value, label, max_length):
    text = "" if value is None else str(value).strip()
    if not text:
        raise InvalidDataError(f"{label} is required.")
    if len(text) > max_length:
        raise InvalidDataError(f"{label} must be at most {max_length} characters.")
    return text


def _clean_optional_text(value, label, max_length):
    if value is None or str(value).strip() == "":
        return None
    return _clean_text(value, label, max_length)


def _clean_machine_code(value):
    text = "" if value is None else str(value).strip()
    if not MACHINE_CODE_PATTERN.fullmatch(text):
        raise InvalidDataError(
            "Machine ID must be 1 to 50 characters: letters, numbers, hyphen or underscore, "
            "starting with a letter or number."
        )
    return text


def _clean_number(value, label, minimum=None, required=False):
    if value is None:
        if required:
            raise InvalidDataError(f"{label} is required.")
        return None
    if isinstance(value, bool):
        raise InvalidDataError(f"{label} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InvalidDataError(f"{label} must be a number.") from None
    if not math.isfinite(number):
        raise InvalidDataError(f"{label} must be a finite number.")
    if minimum is not None and number < minimum:
        raise InvalidDataError(f"{label} must be at least {minimum}.")
    return number


def _clean_positive_int(value, label):
    number = _clean_number(value, label, minimum=1)
    if number is None:
        return None
    if int(number) != number:
        raise InvalidDataError(f"{label} must be a whole number.")
    return int(number)


def _date_text(value, label):
    """Turn a date (or 'YYYY-MM-DD' text) into 'YYYY-MM-DD'."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise InvalidDataError(f"{label} must be a date like 2026-10-23.") from None


def _row_to_dict(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------- machines

_MACHINE_SELECT = """
    SELECT m.id, m.machine_id, m.name, m.machine_type, m.location, m.created_at,
           (SELECT COUNT(*) FROM analyses a WHERE a.machine_pk = m.id) AS analysis_count
    FROM machines m
"""


def create_machine(machine_id, name, machine_type, location=None, db_path=None):
    """Register a machine. Returns the saved record as a dictionary."""
    code = _clean_machine_code(machine_id)
    name = _clean_text(name, "Machine name", 100)
    machine_type = _clean_text(machine_type, "Machine type", 50)
    location = _clean_optional_text(location, "Location", 100)

    try:
        with connect(db_path) as connection:
            cursor = connection.execute(
                "INSERT INTO machines (machine_id, name, machine_type, location, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (code, name, machine_type, location, utc_now()),
            )
            row = connection.execute(
                _MACHINE_SELECT + " WHERE m.id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError:
        raise DuplicateError(f"A machine with ID '{code}' already exists.") from None
    return dict(row)


def get_machine(machine_pk, db_path=None):
    """Find a machine by its record number. Returns None if it does not exist."""
    with connect(db_path) as connection:
        row = connection.execute(_MACHINE_SELECT + " WHERE m.id = ?", (machine_pk,)).fetchone()
    return _row_to_dict(row)


def get_machine_by_code(machine_id, db_path=None):
    """Find a machine by its Machine ID text (not case sensitive). None if missing."""
    code = "" if machine_id is None else str(machine_id).strip()
    with connect(db_path) as connection:
        row = connection.execute(
            _MACHINE_SELECT + " WHERE m.machine_id = ?", (code,)
        ).fetchone()
    return _row_to_dict(row)


def list_machines(db_path=None):
    """All machines, sorted by Machine ID. Returns an empty list for an empty database."""
    with connect(db_path) as connection:
        rows = connection.execute(
            _MACHINE_SELECT + " ORDER BY m.machine_id COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def update_machine(machine_pk, name, machine_type, location=None, db_path=None):
    """Change the name, type and location of a machine. The Machine ID stays fixed."""
    name = _clean_text(name, "Machine name", 100)
    machine_type = _clean_text(machine_type, "Machine type", 50)
    location = _clean_optional_text(location, "Location", 100)

    with connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE machines SET name = ?, machine_type = ?, location = ? WHERE id = ?",
            (name, machine_type, location, machine_pk),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("That machine does not exist.")
        row = connection.execute(_MACHINE_SELECT + " WHERE m.id = ?", (machine_pk,)).fetchone()
    return dict(row)


def delete_machine(machine_pk, db_path=None):
    """Delete a machine that has no saved analyses."""
    with connect(db_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM machines WHERE id = ?", (machine_pk,)
        ).fetchone()
        if exists is None:
            raise NotFoundError("That machine does not exist.")
        count = connection.execute(
            "SELECT COUNT(*) FROM analyses WHERE machine_pk = ?", (machine_pk,)
        ).fetchone()[0]
        if count > 0:
            raise InUseError(
                f"This machine has {count} saved analysis record(s) and cannot be deleted."
            )
        connection.execute("DELETE FROM machines WHERE id = ?", (machine_pk,))


# --------------------------------------------------------------------- analyses

_ANALYSIS_SELECT = """
    SELECT a.id, a.machine_pk, m.machine_id AS machine_code, m.name AS machine_name,
           a.filename, a.stored_path, a.file_sha256, a.duration_seconds, a.sample_rate,
           a.channels, a.prediction_label, a.anomaly_score, a.threshold,
           a.model_name, a.model_version, a.is_mock, a.created_at,
           al.id AS alert_id
    FROM analyses a
    JOIN machines m ON m.id = a.machine_pk
    LEFT JOIN alerts al ON al.analysis_id = a.id
"""

_ALERT_SELECT = """
    SELECT al.id, al.analysis_id, al.machine_pk, m.machine_id AS machine_code,
           m.name AS machine_name, al.message, al.acknowledged, al.created_at,
           a.filename, a.prediction_label, a.anomaly_score, a.is_mock
    FROM alerts al
    JOIN machines m ON m.id = al.machine_pk
    JOIN analyses a ON a.id = al.analysis_id
"""


def save_analysis(
    machine_pk,
    filename,
    prediction_label,
    anomaly_score,
    *,
    model_name,
    model_version,
    is_mock,
    threshold=None,
    duration_seconds=None,
    sample_rate=None,
    channels=None,
    file_sha256=None,
    stored_path=None,
    alert_message=None,
    db_path=None,
):
    """Save one analysis result, and its alert if alert_message is given.

    The analysis and the alert are saved in ONE transaction: either both are saved
    or neither is. is_mock must be given explicitly (True for placeholder results)
    so a mock result can never be mistaken for a real model result later.

    Returns {"analysis": {...}, "alert": {...} or None}.
    """
    if prediction_label not in PREDICTION_LABELS:
        raise InvalidDataError(f"Prediction must be one of: {', '.join(PREDICTION_LABELS)}.")
    if not isinstance(is_mock, bool):
        raise InvalidDataError("is_mock must be True or False.")

    filename = _clean_text(filename, "File name", 255)
    model_name = _clean_text(model_name, "Model name", 100)
    model_version = _clean_text(model_version, "Model version", 100)
    anomaly_score = _clean_number(anomaly_score, "Anomaly score", required=True)
    threshold = _clean_number(threshold, "Threshold")
    duration_seconds = _clean_number(duration_seconds, "Duration", minimum=0)
    sample_rate = _clean_positive_int(sample_rate, "Sample rate")
    channels = _clean_positive_int(channels, "Channels")
    file_sha256 = _clean_optional_text(file_sha256, "File hash", 64)
    stored_path = _clean_optional_text(stored_path, "Stored path", 500)
    alert_message = _clean_optional_text(alert_message, "Alert message", 500)

    try:
        with connect(db_path) as connection:
            now = utc_now()
            cursor = connection.execute(
                "INSERT INTO analyses (machine_pk, filename, stored_path, file_sha256, "
                "duration_seconds, sample_rate, channels, prediction_label, anomaly_score, "
                "threshold, model_name, model_version, is_mock, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    machine_pk, filename, stored_path, file_sha256, duration_seconds,
                    sample_rate, channels, prediction_label, anomaly_score, threshold,
                    model_name, model_version, 1 if is_mock else 0, now,
                ),
            )
            analysis_id = cursor.lastrowid
            if alert_message is not None:
                connection.execute(
                    "INSERT INTO alerts (analysis_id, machine_pk, message, acknowledged, "
                    "created_at) VALUES (?, ?, ?, 0, ?)",
                    (analysis_id, machine_pk, alert_message, now),
                )
            analysis = _fetch_analysis(connection, analysis_id)
            alert = _fetch_alert_for_analysis(connection, analysis_id)
    except sqlite3.IntegrityError:
        raise NotFoundError(f"Machine number {machine_pk} does not exist.") from None
    return {"analysis": analysis, "alert": alert}


def _fetch_analysis(connection, analysis_id):
    row = connection.execute(_ANALYSIS_SELECT + " WHERE a.id = ?", (analysis_id,)).fetchone()
    return _row_to_dict(row)


def _fetch_alert_for_analysis(connection, analysis_id):
    row = connection.execute(_ALERT_SELECT + " WHERE al.analysis_id = ?", (analysis_id,)).fetchone()
    return _row_to_dict(row)


def get_analysis(analysis_id, db_path=None):
    """One analysis with its machine details. Returns None if it does not exist."""
    with connect(db_path) as connection:
        return _fetch_analysis(connection, analysis_id)


def _analysis_filters(machine_pk, prediction_label, date_from, date_to):
    """Build the WHERE part of the query. Only fixed SQL text is added here;
    the values always travel separately as parameters."""
    clauses = []
    params = []
    if machine_pk is not None:
        clauses.append("a.machine_pk = ?")
        params.append(machine_pk)
    if prediction_label is not None:
        if prediction_label not in PREDICTION_LABELS:
            raise InvalidDataError(f"Prediction must be one of: {', '.join(PREDICTION_LABELS)}.")
        clauses.append("a.prediction_label = ?")
        params.append(prediction_label)
    if date_from is not None:
        clauses.append("substr(a.created_at, 1, 10) >= ?")
        params.append(_date_text(date_from, "Start date"))
    if date_to is not None:
        clauses.append("substr(a.created_at, 1, 10) <= ?")
        params.append(_date_text(date_to, "End date"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_analyses(
    machine_pk=None,
    prediction_label=None,
    date_from=None,
    date_to=None,
    limit=100,
    offset=0,
    db_path=None,
):
    """Analyses, newest first. Dates are compared in UTC."""
    limit = _clean_positive_int(limit, "Limit")
    if limit > MAX_PAGE_SIZE:
        raise InvalidDataError(f"Limit must be at most {MAX_PAGE_SIZE}.")
    offset = _clean_number(offset, "Offset", minimum=0, required=True)
    where, params = _analysis_filters(machine_pk, prediction_label, date_from, date_to)
    with connect(db_path) as connection:
        rows = connection.execute(
            _ANALYSIS_SELECT + where + " ORDER BY a.created_at DESC, a.id DESC LIMIT ? OFFSET ?",
            params + [limit, int(offset)],
        ).fetchall()
    return [dict(row) for row in rows]


def count_analyses(machine_pk=None, prediction_label=None, date_from=None, date_to=None,
                   db_path=None):
    """How many analyses match the filters."""
    where, params = _analysis_filters(machine_pk, prediction_label, date_from, date_to)
    with connect(db_path) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM analyses a" + where, params
        ).fetchone()[0]


# ----------------------------------------------------------------------- alerts

def list_alerts(machine_pk=None, only_unacknowledged=False, limit=100, db_path=None):
    """Alerts, newest first."""
    limit = _clean_positive_int(limit, "Limit")
    if limit > MAX_PAGE_SIZE:
        raise InvalidDataError(f"Limit must be at most {MAX_PAGE_SIZE}.")
    clauses = []
    params = []
    if machine_pk is not None:
        clauses.append("al.machine_pk = ?")
        params.append(machine_pk)
    if only_unacknowledged:
        clauses.append("al.acknowledged = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect(db_path) as connection:
        rows = connection.execute(
            _ALERT_SELECT + where + " ORDER BY al.created_at DESC, al.id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(row) for row in rows]


def acknowledge_alert(alert_id, db_path=None):
    """Mark an alert as reviewed. Returns the updated alert."""
    with connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
        )
        if cursor.rowcount == 0:
            raise NotFoundError("That alert does not exist.")
        row = connection.execute(_ALERT_SELECT + " WHERE al.id = ?", (alert_id,)).fetchone()
    return dict(row)


# -------------------------------------------------------------------- dashboard

def get_dashboard_stats(db_path=None):
    """Counts for the dashboard cards. Works on an empty database (all zeros)."""
    with connect(db_path) as connection:
        machines = connection.execute("SELECT COUNT(*) FROM machines").fetchone()[0]
        analysis_row = connection.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(prediction_label = 'Normal'), 0) AS normal_count, "
            "COALESCE(SUM(prediction_label = 'Potentially Abnormal'), 0) AS abnormal_count, "
            "COALESCE(SUM(is_mock), 0) AS mock_count, "
            "MAX(created_at) AS latest "
            "FROM analyses"
        ).fetchone()
        alert_row = connection.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(acknowledged = 0), 0) AS open_count FROM alerts"
        ).fetchone()
    return {
        "total_machines": machines,
        "total_analyses": analysis_row["total"],
        "normal_count": analysis_row["normal_count"],
        "abnormal_count": analysis_row["abnormal_count"],
        "mock_analyses": analysis_row["mock_count"],
        "latest_analysis_at": analysis_row["latest"],
        "total_alerts": alert_row["total"],
        "open_alerts": alert_row["open_count"],
    }
