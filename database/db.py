"""SQLite connection and table setup for MachineMind.

The database is one file. By default it is data/machinemind.db inside the project.
Set the environment variable MACHINEMIND_DB_PATH to use a different file
(the automated tests do this so they never touch your real data).
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "machinemind.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS machines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id   TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name         TEXT NOT NULL,
    machine_type TEXT NOT NULL,
    location     TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_pk       INTEGER NOT NULL REFERENCES machines(id) ON DELETE RESTRICT,
    filename         TEXT NOT NULL,
    stored_path      TEXT,
    file_sha256      TEXT,
    duration_seconds REAL,
    sample_rate      INTEGER,
    channels         INTEGER,
    prediction_label TEXT NOT NULL
                     CHECK (prediction_label IN ('Normal', 'Potentially Abnormal')),
    anomaly_score    REAL NOT NULL,
    threshold        REAL,
    model_name       TEXT NOT NULL,
    model_version    TEXT NOT NULL,
    is_mock          INTEGER NOT NULL DEFAULT 0 CHECK (is_mock IN (0, 1)),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id  INTEGER NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    machine_pk   INTEGER NOT NULL REFERENCES machines(id) ON DELETE RESTRICT,
    message      TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0 CHECK (acknowledged IN (0, 1)),
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_machine ON analyses(machine_pk);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_machine ON alerts(machine_pk);
"""


def get_db_path():
    """Return the database file path (environment variable wins over the default)."""
    override = os.environ.get("MACHINEMIND_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def utc_now():
    """Current time in UTC as text, for example 2026-10-23T08:15:00+00:00."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path=None):
    """Open the database for one unit of work.

    Everything inside the 'with' block is ONE transaction: saved together if the
    block finishes, undone together if an error happens. The connection always closes.
    """
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless asked
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path=None):
    """Create the database file and any missing tables. Safe to call many times."""
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
    return Path(db_path) if db_path else get_db_path()
