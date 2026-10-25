"""Analyse one uploaded recording: check it, predict, store it, save the result.

This file does not depend on FastAPI, so it is easy to test on its own.

Order of work (nothing is saved until the prediction has succeeded):
  1. the machine must exist
  2. the audio must be valid
  3. the predictor runs and its output is checked
  4. the audio file is stored (named by its SHA-256 hash, so identical files share one copy)
  5. the analysis, and an alert if the result is abnormal, are saved in one transaction
"""
import hashlib
import logging
import math
import os
import tempfile
from pathlib import Path

from backend.config import get_upload_dir
from backend.services.audio_utils import validate_audio
from database import models
from ml_integration.predictor import MOCK_WARNING, PredictorError

logger = logging.getLogger("machinemind")


class PredictionFailedError(Exception):
    """The analysis could not be completed. The message is shown to the user."""


def clean_filename(filename):
    """Keep only the file name (never a folder path) and limit its length."""
    name = Path(str(filename or "").replace("\\", "/")).name.strip()
    if not name:
        return "recording.wav"
    if len(name) > 255:
        suffix = Path(name).suffix
        suffix = suffix if len(suffix) <= 10 else ""
        name = name[: 255 - len(suffix)] + suffix
    return name


def _check_prediction(result):
    """Refuse to save anything unless the predictor returned a complete, sensible result."""
    score = getattr(result, "score", None)
    threshold = getattr(result, "threshold", None)
    problems = []
    if getattr(result, "label", None) not in models.PREDICTION_LABELS:
        problems.append("label")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        problems.append("score")
    if threshold is not None and (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
    ):
        problems.append("threshold")
    for field in ("model_name", "model_version", "score_note"):
        value = getattr(result, field, None)
        if not isinstance(value, str) or not value.strip():
            problems.append(field)
    if not isinstance(getattr(result, "is_mock", None), bool):
        problems.append("is_mock")
    if problems:
        logger.error("Predictor returned an invalid result. Bad fields: %s", problems)
        raise PredictionFailedError(
            "The model returned an invalid result, so nothing was saved."
        )


def _store_audio(file_bytes, sha256, upload_dir):
    """Save the recording as <sha256>.wav. Returns the file name (relative to the upload folder)."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{sha256}.wav"
    target = upload_dir / stored_name
    if target.exists():
        return stored_name  # the identical file is already stored
    descriptor, temp_name = tempfile.mkstemp(dir=str(upload_dir), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(file_bytes)
        os.replace(temp_name, target)  # all-or-nothing: no half-written file is ever visible
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return stored_name


def _alert_message(result, machine):
    threshold_text = f" (threshold {result.threshold:g})" if result.threshold is not None else ""
    text = (
        f"{machine['machine_id']}: anomaly score {result.score:.4g}{threshold_text} "
        "- recording flagged as potentially abnormal."
    )
    if result.is_mock:
        text = "[MOCK - not a real prediction] " + text
    return text


def analyse_recording(file_bytes, filename, machine_pk, predictor, db_path=None, upload_dir=None):
    """Run the whole analysis. Returns a dictionary with the saved analysis and alert.

    Raises: models.NotFoundError, AudioValidationError, PredictionFailedError,
    models.InvalidDataError.
    """
    machine = models.get_machine(machine_pk, db_path=db_path)
    if machine is None:
        raise models.NotFoundError(f"Machine number {machine_pk} does not exist.")

    safe_name = clean_filename(filename)
    info, samples = validate_audio(file_bytes, safe_name)

    try:
        result = predictor.predict(samples, info.sample_rate)
    except PredictorError as error:
        raise PredictionFailedError(str(error)) from error
    except Exception as error:
        logger.exception("The predictor crashed")
        raise PredictionFailedError(
            "The analysis failed unexpectedly, so nothing was saved."
        ) from error
    _check_prediction(result)

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    stored_name = _store_audio(file_bytes, sha256, upload_dir or get_upload_dir())

    alert_message = None
    if result.label == "Potentially Abnormal":
        alert_message = _alert_message(result, machine)

    saved = models.save_analysis(
        machine_pk,
        safe_name,
        result.label,
        result.score,
        model_name=result.model_name,
        model_version=result.model_version,
        is_mock=result.is_mock,
        threshold=result.threshold,
        duration_seconds=info.duration_seconds,
        sample_rate=info.sample_rate,
        channels=info.channels,
        file_sha256=sha256,
        stored_path=stored_name,
        alert_message=alert_message,
        db_path=db_path,
    )

    warnings = []
    if info.is_silent:
        warnings.append("The recording is completely silent, so the result may not be meaningful.")

    return {
        "analysis": saved["analysis"],
        "alert": saved["alert"],
        "score_note": result.score_note,
        "warnings": warnings,
        "mock_warning": MOCK_WARNING if result.is_mock else None,
    }
