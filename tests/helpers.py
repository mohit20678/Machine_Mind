"""Small helpers shared by the tests: make in-memory WAV files and stand-in predictors."""
import io

import numpy as np
import soundfile as sf

from ml_integration.predictor import PredictionResult


def make_wav_bytes(seconds=3.0, channels=1, rate=16000, level=0.2, seed=0, silent=False):
    """Create a small WAV file in memory (no file on disk, no dataset needed)."""
    rng = np.random.default_rng(seed)
    frames = int(seconds * rate)
    data = np.zeros((frames, channels), dtype="float32")
    if not silent:
        data = (level * rng.standard_normal((frames, channels))).astype("float32")
        data = np.clip(data, -0.99, 0.99)
    buffer = io.BytesIO()
    sf.write(buffer, data, rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


class FixedPredictor:
    """A stand-in model that always returns the same label. Used to test alerts."""

    def __init__(self, label="Potentially Abnormal", score=0.9, threshold=0.5, is_mock=False):
        self.label, self.score, self.threshold, self.is_mock = label, score, threshold, is_mock

    def predict(self, samples, sample_rate):
        return PredictionResult(
            label=self.label, score=self.score, threshold=self.threshold,
            model_name="test-model", model_version="1", is_mock=self.is_mock,
            score_note="Test score definition.",
        )

    def status(self):
        return {"mode": "test", "is_real": not self.is_mock, "model_name": "test-model",
                "model_version": "1", "threshold": self.threshold,
                "score_note": "Test score definition.", "message": "Test predictor."}


class BrokenPredictor:
    """A stand-in model that always fails."""

    def __init__(self, error):
        self.error = error

    def predict(self, samples, sample_rate):
        raise self.error

    def status(self):
        raise self.error
