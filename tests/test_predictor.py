"""Tests for the placeholder predictor.

These check the SOFTWARE only. The placeholder is not an AI model, so nothing here
says anything about how well a real model detects faults.
"""
import unittest

import numpy as np

from ml_integration.predictor import (
    MOCK_THRESHOLD,
    MockPredictor,
    PredictorError,
    get_predictor,
)


class TestMockPredictor(unittest.TestCase):
    def setUp(self):
        self.predictor = MockPredictor()
        rng = np.random.default_rng(1)
        self.samples = rng.standard_normal((16000, 2)).astype("float32")

    def test_result_is_clearly_marked_as_mock(self):
        result = self.predictor.predict(self.samples, 16000)
        self.assertTrue(result.is_mock)
        self.assertEqual(result.model_name, "mock-placeholder")
        self.assertIn("PLACEHOLDER", result.score_note)

    def test_same_audio_gives_same_result(self):
        first = self.predictor.predict(self.samples, 16000)
        second = self.predictor.predict(self.samples.copy(), 16000)
        self.assertEqual(first, second)

    def test_score_is_between_0_and_1_and_label_follows_threshold(self):
        rng = np.random.default_rng(2)
        labels = set()
        for _ in range(60):
            samples = rng.standard_normal((800, 1)).astype("float32")
            result = self.predictor.predict(samples, 16000)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLess(result.score, 1.0)
            expected = "Potentially Abnormal" if result.score >= MOCK_THRESHOLD else "Normal"
            self.assertEqual(result.label, expected)
            labels.add(result.label)
        self.assertEqual(labels, {"Normal", "Potentially Abnormal"})  # both outcomes occur

    def test_bad_shape_is_rejected(self):
        with self.assertRaises(PredictorError):
            self.predictor.predict(np.zeros(100, dtype="float32"), 16000)
        with self.assertRaises(PredictorError):
            self.predictor.predict(np.zeros((0, 1), dtype="float32"), 16000)

    def test_status_says_real_inference_is_not_connected(self):
        status = self.predictor.status()
        self.assertFalse(status["is_real"])
        self.assertEqual(status["mode"], "mock")
        self.assertIn("NOT connected", status["message"])

    def test_get_predictor_returns_the_mock_for_now(self):
        self.assertIsInstance(get_predictor(), MockPredictor)


if __name__ == "__main__":
    unittest.main()
