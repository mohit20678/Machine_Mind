"""The ONLY door between the application and the ML model.

The backend never imports training code. It asks get_predictor() for an object that has:

    predict(samples, sample_rate) -> PredictionResult
    status() -> dict (shown at GET /api/model/status)

Right now the predictor is a clearly labelled MOCK. In Milestone 7 your teammate's real
model replaces MockPredictor, and nothing else in the application has to change.
"""
import hashlib
from dataclasses import dataclass

import numpy as np

MOCK_MODEL_NAME = "mock-placeholder"
MOCK_MODEL_VERSION = "0"
MOCK_THRESHOLD = 0.5
MOCK_SCORE_NOTE = (
    "PLACEHOLDER number between 0 and 1, computed from the audio samples so the same audio "
    "always gives the same number. It says nothing about the machine and is not an anomaly measure."
)
MOCK_WARNING = (
    "MOCK RESULT: this comes from a placeholder, not from a trained ML model. "
    "It is not a genuine prediction."
)


class PredictorError(Exception):
    """The model could not produce a result. The message is shown to the user."""


class ModelUnavailableError(PredictorError):
    """The model is not available (for example the model file is missing)."""


@dataclass(frozen=True)
class PredictionResult:
    label: str                 # "Normal" or "Potentially Abnormal"
    score: float               # meaning depends on the model; see score_note
    threshold: float | None    # score at or above this is flagged, if the model has one
    model_name: str
    model_version: str
    is_mock: bool              # True only for placeholder results
    score_note: str            # plain-language definition of the score


class MockPredictor:
    """Placeholder that is honest about being a placeholder. NOT an AI model."""

    def predict(self, samples, sample_rate):
        samples = np.asarray(samples)
        if samples.ndim != 2 or samples.shape[0] == 0:
            raise PredictorError("The audio data has an unexpected shape.")
        digest = hashlib.sha256(np.ascontiguousarray(samples).tobytes()).hexdigest()
        score = int(digest[:8], 16) / 0x100000000  # a number in [0, 1)
        label = "Potentially Abnormal" if score >= MOCK_THRESHOLD else "Normal"
        return PredictionResult(
            label=label,
            score=score,
            threshold=MOCK_THRESHOLD,
            model_name=MOCK_MODEL_NAME,
            model_version=MOCK_MODEL_VERSION,
            is_mock=True,
            score_note=MOCK_SCORE_NOTE,
        )

    def status(self):
        return {
            "mode": "mock",
            "is_real": False,
            "model_name": MOCK_MODEL_NAME,
            "model_version": MOCK_MODEL_VERSION,
            "threshold": MOCK_THRESHOLD,
            "score_note": MOCK_SCORE_NOTE,
            "message": "Real ML inference is NOT connected. Results are placeholders.",
        }


_predictor = MockPredictor()


def get_predictor():
    """Return the predictor the backend should use (a FastAPI dependency; tests replace it)."""
    return _predictor
