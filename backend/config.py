"""Backend settings. Values come from environment variables, with safe defaults.

MACHINEMIND_UPLOAD_DIR  folder where uploaded recordings are kept (default: data/uploads)
MACHINEMIND_DB_PATH     database file (read in database/db.py, default: data/machinemind.db)
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"


def get_upload_dir():
    """Folder for uploaded recordings. Read each time, so tests can point it elsewhere."""
    override = os.environ.get("MACHINEMIND_UPLOAD_DIR")
    return Path(override) if override else DEFAULT_UPLOAD_DIR
