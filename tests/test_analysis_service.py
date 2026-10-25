"""Tests for the analysis service (check audio, predict, store, save).

No FastAPI and no real dataset needed: audio is generated in memory.
These are software tests, not an evaluation of any ML model.
"""
import tempfile
import unittest
from pathlib import Path

from backend.services import analysis_service
from backend.services.analysis_service import PredictionFailedError, analyse_recording
from backend.services.audio_utils import AudioValidationError
from database import models
from database.db import init_db
from ml_integration.predictor import MockPredictor, ModelUnavailableError, PredictionResult
from tests.helpers import BrokenPredictor, FixedPredictor, make_wav_bytes


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.db = Path(self._folder.name) / "test.db"
        self.uploads = Path(self._folder.name) / "uploads"
        init_db(self.db)
        self.machine = models.create_machine("PUMP-01", "Test pump", "Pump", db_path=self.db)

    def run_analysis(self, data, predictor, name="clip.wav", machine_pk=None):
        return analyse_recording(
            data, name, machine_pk or self.machine["id"], predictor,
            db_path=self.db, upload_dir=self.uploads,
        )

    def stored_files(self):
        return sorted(p.name for p in self.uploads.glob("*")) if self.uploads.exists() else []

    def assert_nothing_saved(self):
        self.assertEqual(models.count_analyses(db_path=self.db), 0)
        self.assertEqual(models.list_alerts(db_path=self.db), [])
        self.assertEqual(self.stored_files(), [])


class TestSuccessfulAnalysis(ServiceTestCase):
    def test_8_channel_recording_is_analysed_and_saved(self):
        data = make_wav_bytes(seconds=3, channels=8)
        result = self.run_analysis(data, MockPredictor())
        analysis = result["analysis"]
        self.assertEqual(analysis["channels"], 8)
        self.assertEqual(analysis["sample_rate"], 16000)
        self.assertAlmostEqual(analysis["duration_seconds"], 3.0)
        self.assertEqual(analysis["machine_code"], "PUMP-01")
        self.assertEqual(analysis["is_mock"], 1)
        self.assertEqual(analysis["model_name"], "mock-placeholder")
        self.assertIn("MOCK RESULT", result["mock_warning"])
        self.assertEqual(models.count_analyses(db_path=self.db), 1)
        self.assertEqual(models.get_machine(self.machine["id"], db_path=self.db)["analysis_count"], 1)

    def test_audio_is_stored_under_its_hash(self):
        result = self.run_analysis(make_wav_bytes(), MockPredictor())
        files = self.stored_files()
        self.assertEqual(len(files), 1)
        saved = models.get_analysis(result["analysis"]["id"], db_path=self.db)
        self.assertEqual(saved["stored_path"], files[0])
        self.assertEqual(files[0], saved["file_sha256"] + ".wav")
        self.assertEqual((self.uploads / files[0]).read_bytes(), make_wav_bytes())

    def test_same_file_twice_stores_one_copy_but_two_analyses(self):
        data = make_wav_bytes()
        self.run_analysis(data, MockPredictor())
        self.run_analysis(data, MockPredictor())
        self.assertEqual(len(self.stored_files()), 1)
        self.assertEqual(models.count_analyses(db_path=self.db), 2)

    def test_no_temporary_files_are_left_behind(self):
        self.run_analysis(make_wav_bytes(), MockPredictor())
        self.assertFalse([n for n in self.stored_files() if n.endswith(".tmp")])

    def test_file_name_is_cleaned(self):
        result = self.run_analysis(make_wav_bytes(), MockPredictor(), name="../../evil.wav")
        self.assertEqual(result["analysis"]["filename"], "evil.wav")
        result = self.run_analysis(make_wav_bytes(seed=5), MockPredictor(), name="C:\\x\\y\\pump.wav")
        self.assertEqual(result["analysis"]["filename"], "pump.wav")

    def test_silent_recording_gets_a_warning(self):
        result = self.run_analysis(make_wav_bytes(silent=True), MockPredictor())
        self.assertTrue(any("silent" in w for w in result["warnings"]))

    def test_normal_recording_with_normal_result_has_no_alert(self):
        result = self.run_analysis(make_wav_bytes(), FixedPredictor("Normal", 0.1))
        self.assertIsNone(result["alert"])
        self.assertEqual(models.list_alerts(db_path=self.db), [])


class TestAlerts(ServiceTestCase):
    def test_abnormal_result_creates_an_alert(self):
        result = self.run_analysis(make_wav_bytes(), FixedPredictor(is_mock=False))
        alert = result["alert"]
        self.assertIsNotNone(alert)
        self.assertEqual(alert["analysis_id"], result["analysis"]["id"])
        self.assertEqual(alert["acknowledged"], 0)
        self.assertIn("PUMP-01", alert["message"])
        self.assertIn("threshold 0.5", alert["message"])
        self.assertNotIn("MOCK", alert["message"])
        self.assertEqual(result["analysis"]["is_mock"], 0)
        self.assertIsNone(result["mock_warning"])

    def test_mock_alert_is_labelled_as_mock(self):
        result = self.run_analysis(make_wav_bytes(), FixedPredictor(is_mock=True))
        self.assertIn("MOCK", result["alert"]["message"])
        self.assertEqual(result["alert"]["is_mock"], 1)

    def test_alert_without_threshold(self):
        result = self.run_analysis(make_wav_bytes(), FixedPredictor(threshold=None))
        self.assertNotIn("threshold", result["alert"]["message"])


class TestRejectedInput(ServiceTestCase):
    def test_unknown_machine(self):
        with self.assertRaises(models.NotFoundError):
            self.run_analysis(make_wav_bytes(), MockPredictor(), machine_pk=999)
        self.assert_nothing_saved()

    def test_fake_wav_file(self):
        with self.assertRaises(AudioValidationError):
            self.run_analysis(b"this is not audio", MockPredictor())
        self.assert_nothing_saved()

    def test_wrong_extension(self):
        with self.assertRaises(AudioValidationError):
            self.run_analysis(make_wav_bytes(), MockPredictor(), name="clip.mp3")
        self.assert_nothing_saved()

    def test_empty_file(self):
        with self.assertRaises(AudioValidationError):
            self.run_analysis(b"", MockPredictor())
        self.assert_nothing_saved()

    def test_too_short_recording(self):
        with self.assertRaises(AudioValidationError):
            self.run_analysis(make_wav_bytes(seconds=0.2), MockPredictor())
        self.assert_nothing_saved()


class TestModelFailures(ServiceTestCase):
    def test_model_unavailable_saves_nothing(self):
        broken = BrokenPredictor(ModelUnavailableError("The ML model file was not found."))
        with self.assertRaises(PredictionFailedError) as caught:
            self.run_analysis(make_wav_bytes(), broken)
        self.assertIn("model file was not found", str(caught.exception))
        self.assert_nothing_saved()

    def test_unexpected_model_crash_gives_generic_message(self):
        broken = BrokenPredictor(ValueError("secret internal detail"))
        with self.assertRaises(PredictionFailedError) as caught:
            self.run_analysis(make_wav_bytes(), broken)
        self.assertNotIn("secret", str(caught.exception))
        self.assert_nothing_saved()

    def test_invalid_model_output_is_refused(self):
        bad_results = [
            PredictionResult("Broken", 0.5, 0.5, "m", "1", False, "note"),
            PredictionResult("Normal", float("nan"), 0.5, "m", "1", False, "note"),
            PredictionResult("Normal", float("inf"), 0.5, "m", "1", False, "note"),
            PredictionResult("Normal", True, 0.5, "m", "1", False, "note"),
            PredictionResult("Normal", 0.5, float("nan"), "m", "1", False, "note"),
            PredictionResult("Normal", 0.5, 0.5, "", "1", False, "note"),
            PredictionResult("Normal", 0.5, 0.5, "m", "1", 1, "note"),
            PredictionResult("Normal", 0.5, 0.5, "m", "1", False, ""),
        ]

        class Returns:
            def __init__(self, result):
                self.result = result

            def predict(self, samples, sample_rate):
                return self.result

        for number, bad in enumerate(bad_results):
            with self.subTest(case=number):
                with self.assertRaises(PredictionFailedError):
                    self.run_analysis(make_wav_bytes(), Returns(bad))
        self.assert_nothing_saved()

    def test_predictor_returning_nothing_is_refused(self):
        class ReturnsNone:
            def predict(self, samples, sample_rate):
                return None

        with self.assertRaises(PredictionFailedError):
            self.run_analysis(make_wav_bytes(), ReturnsNone())
        self.assert_nothing_saved()


class TestCleanFilename(unittest.TestCase):
    def test_cases(self):
        clean = analysis_service.clean_filename
        self.assertEqual(clean("a.wav"), "a.wav")
        self.assertEqual(clean("/etc/passwd.wav"), "passwd.wav")
        self.assertEqual(clean(""), "recording.wav")
        self.assertEqual(clean(None), "recording.wav")
        long_name = "x" * 400 + ".wav"
        self.assertEqual(len(clean(long_name)), 255)
        self.assertTrue(clean(long_name).endswith(".wav"))


if __name__ == "__main__":
    unittest.main()
