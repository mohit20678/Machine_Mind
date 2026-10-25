"""Tests for the FastAPI backend, using FastAPI's TestClient (no server needs to run).

Every test gets a temporary database and a temporary upload folder, so your real data
is never touched. Audio is generated in memory, so the MIMII dataset is not needed.
These are software tests, not an evaluation of any ML model.

Run with:  pytest -v
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import audio_utils
from ml_integration.predictor import ModelUnavailableError, get_predictor
from tests.helpers import BrokenPredictor, FixedPredictor, make_wav_bytes


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.uploads = Path(self._folder.name) / "uploads"
        patcher = mock.patch.dict(os.environ, {
            "MACHINEMIND_DB_PATH": str(Path(self._folder.name) / "api_test.db"),
            "MACHINEMIND_UPLOAD_DIR": str(self.uploads),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.client.__enter__()  # runs the startup code that creates the database
        self.addCleanup(self.client.__exit__, None, None, None)
        self.addCleanup(app.dependency_overrides.clear)

    # helpers
    def use_predictor(self, predictor):
        app.dependency_overrides[get_predictor] = lambda: predictor

    def make_machine(self, code="PUMP-01"):
        response = self.client.post("/api/machines", json={
            "machine_id": code, "name": "Test pump", "machine_type": "Pump", "location": "Plant 1"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def upload(self, machine_pk, data=None, name="clip.wav"):
        data = make_wav_bytes() if data is None else data
        return self.client.post(
            "/api/analyses",
            data={"machine_pk": str(machine_pk)},
            files={"file": (name, data, "audio/wav")},
        )

    def assert_error(self, response, status, text):
        self.assertEqual(response.status_code, status, response.text)
        detail = response.json()["detail"]
        self.assertIsInstance(detail, str)
        self.assertIn(text.lower(), detail.lower())

    def stats(self):
        return self.client.get("/api/stats").json()


class TestSystemEndpoints(ApiTestCase):
    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_stats_on_empty_database(self):
        stats = self.stats()
        self.assertEqual(stats["total_machines"], 0)
        self.assertEqual(stats["total_analyses"], 0)
        self.assertEqual(stats["total_alerts"], 0)

    def test_model_status_says_mock(self):
        status = self.client.get("/api/model/status").json()
        self.assertFalse(status["is_real"])
        self.assertEqual(status["mode"], "mock")

    def test_unknown_address_gives_404(self):
        self.assertEqual(self.client.get("/api/nothing-here").status_code, 404)


class TestMachineEndpoints(ApiTestCase):
    def test_create_list_get(self):
        machine = self.make_machine()
        self.assertEqual(machine["machine_id"], "PUMP-01")
        self.assertEqual(machine["analysis_count"], 0)
        listed = self.client.get("/api/machines").json()
        self.assertEqual([m["machine_id"] for m in listed], ["PUMP-01"])
        found = self.client.get(f"/api/machines/{machine['id']}")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["name"], "Test pump")

    def test_empty_list(self):
        self.assertEqual(self.client.get("/api/machines").json(), [])

    def test_duplicate_machine_id(self):
        self.make_machine("PUMP-01")
        response = self.client.post("/api/machines", json={
            "machine_id": "pump-01", "name": "Again", "machine_type": "Pump"})
        self.assert_error(response, 409, "already exists")

    def test_invalid_machine_data(self):
        bad = self.client.post("/api/machines", json={
            "machine_id": "BAD ID", "name": "N", "machine_type": "Pump"})
        self.assert_error(bad, 422, "Machine ID")
        blank = self.client.post("/api/machines", json={
            "machine_id": "PUMP-02", "name": "   ", "machine_type": "Pump"})
        self.assert_error(blank, 422, "name is required")

    def test_missing_field_gives_readable_message(self):
        response = self.client.post("/api/machines", json={"machine_id": "PUMP-01"})
        self.assert_error(response, 422, "name")

    def test_machine_not_found(self):
        self.assert_error(self.client.get("/api/machines/999"), 404, "does not exist")
        self.assert_error(
            self.client.put("/api/machines/999", json={"name": "N", "machine_type": "Pump"}),
            404, "does not exist")
        self.assert_error(self.client.delete("/api/machines/999"), 404, "does not exist")

    def test_non_numeric_machine_number(self):
        self.assertEqual(self.client.get("/api/machines/abc").status_code, 422)

    def test_update(self):
        machine = self.make_machine()
        response = self.client.put(f"/api/machines/{machine['id']}", json={
            "name": "Renamed", "machine_type": "Fan", "location": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Renamed")
        self.assertEqual(response.json()["machine_id"], "PUMP-01")
        self.assertIsNone(response.json()["location"])

    def test_delete(self):
        machine = self.make_machine()
        self.assertEqual(self.client.delete(f"/api/machines/{machine['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/machines").json(), [])

    def test_cannot_delete_machine_with_analyses(self):
        machine = self.make_machine()
        self.assertEqual(self.upload(machine["id"]).status_code, 201)
        self.assert_error(self.client.delete(f"/api/machines/{machine['id']}"), 409, "cannot be deleted")


class TestUploadAndAnalysis(ApiTestCase):
    def test_valid_recording_with_the_placeholder_model(self):
        machine = self.make_machine()
        response = self.upload(machine["id"], make_wav_bytes(seconds=3, channels=8))
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        analysis = body["analysis"]
        self.assertEqual(analysis["channels"], 8)
        self.assertEqual(analysis["sample_rate"], 16000)
        self.assertEqual(analysis["machine_code"], "PUMP-01")
        self.assertTrue(analysis["is_mock"])
        self.assertEqual(analysis["model_name"], "mock-placeholder")
        self.assertIn("MOCK RESULT", body["mock_warning"])
        self.assertIn("PLACEHOLDER", body["score_note"])
        self.assertEqual(self.stats()["total_analyses"], 1)
        self.assertEqual(self.stats()["mock_analyses"], 1)
        self.assertEqual(len(list(self.uploads.glob("*.wav"))), 1)

    def test_real_model_result_is_not_marked_mock(self):
        self.use_predictor(FixedPredictor("Normal", 0.1, is_mock=False))
        machine = self.make_machine()
        body = self.upload(machine["id"]).json()
        self.assertFalse(body["analysis"]["is_mock"])
        self.assertIsNone(body["mock_warning"])
        self.assertEqual(self.stats()["mock_analyses"], 0)

    def test_unknown_machine(self):
        self.assert_error(self.upload(999), 404, "does not exist")
        self.assertEqual(self.stats()["total_analyses"], 0)

    def test_invalid_uploads_are_rejected_clearly(self):
        machine = self.make_machine()
        cases = [
            (b"this is not audio", "fake.wav", "could not be read"),
            (make_wav_bytes(), "clip.mp3", "Only WAV"),
            (make_wav_bytes(seconds=0.2), "short.wav", "too short"),
        ]
        for data, name, expected in cases:
            with self.subTest(name=name):
                self.assert_error(self.upload(machine["id"], data, name), 422, expected)
        self.assertEqual(self.stats()["total_analyses"], 0)
        self.assertEqual(list(self.uploads.glob("*")) if self.uploads.exists() else [], [])

    def test_empty_file_is_rejected(self):
        machine = self.make_machine()
        response = self.upload(machine["id"], b"", "empty.wav")
        self.assertEqual(response.status_code, 422, response.text)  # wording differs by version
        self.assertIsInstance(response.json()["detail"], str)
        self.assertEqual(self.stats()["total_analyses"], 0)

    def test_missing_file_or_machine_number(self):
        machine = self.make_machine()
        no_file = self.client.post("/api/analyses", data={"machine_pk": str(machine["id"])})
        self.assert_error(no_file, 422, "file")
        no_machine = self.client.post(
            "/api/analyses", files={"file": ("clip.wav", make_wav_bytes(), "audio/wav")})
        self.assert_error(no_machine, 422, "machine_pk")
        not_a_number = self.client.post(
            "/api/analyses", data={"machine_pk": "abc"},
            files={"file": ("clip.wav", make_wav_bytes(), "audio/wav")})
        self.assertEqual(not_a_number.status_code, 422)

    def test_file_too_large(self):
        machine = self.make_machine()
        with mock.patch.object(audio_utils, "MAX_FILE_SIZE_MB", 0.001):
            response = self.upload(machine["id"], make_wav_bytes(seconds=3))
        self.assert_error(response, 413, "too large")
        self.assertEqual(self.stats()["total_analyses"], 0)

    def test_model_unavailable_saves_nothing_and_says_so(self):
        self.use_predictor(BrokenPredictor(ModelUnavailableError("The ML model file was not found.")))
        machine = self.make_machine()
        response = self.upload(machine["id"])
        self.assert_error(response, 503, "model file was not found")
        self.assertEqual(self.stats()["total_analyses"], 0)

    def test_model_crash_gives_503_without_internal_details(self):
        self.use_predictor(BrokenPredictor(ValueError("secret internal detail")))
        machine = self.make_machine()
        response = self.upload(machine["id"])
        self.assert_error(response, 503, "failed unexpectedly")
        self.assertNotIn("secret", response.text)
        self.assertEqual(self.stats()["total_analyses"], 0)


class TestAlertEndpoints(ApiTestCase):
    def test_abnormal_result_creates_an_alert_that_can_be_reviewed(self):
        self.use_predictor(FixedPredictor("Potentially Abnormal", 0.9))
        machine = self.make_machine()
        body = self.upload(machine["id"]).json()
        self.assertIsNotNone(body["alert"])
        self.assertFalse(body["alert"]["acknowledged"])

        alerts = self.client.get("/api/alerts").json()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["machine_code"], "PUMP-01")
        self.assertEqual(len(self.client.get("/api/alerts?only_new=true").json()), 1)
        self.assertEqual(self.stats()["open_alerts"], 1)

        reviewed = self.client.post(f"/api/alerts/{alerts[0]['id']}/acknowledge")
        self.assertEqual(reviewed.status_code, 200)
        self.assertTrue(reviewed.json()["acknowledged"])
        self.assertEqual(self.client.get("/api/alerts?only_new=true").json(), [])
        self.assertEqual(len(self.client.get("/api/alerts").json()), 1)
        self.assertEqual(self.stats()["open_alerts"], 0)

    def test_normal_result_creates_no_alert(self):
        self.use_predictor(FixedPredictor("Normal", 0.1))
        machine = self.make_machine()
        body = self.upload(machine["id"]).json()
        self.assertIsNone(body["alert"])
        self.assertEqual(self.client.get("/api/alerts").json(), [])

    def test_empty_alert_list_and_missing_alert(self):
        self.assertEqual(self.client.get("/api/alerts").json(), [])
        self.assert_error(self.client.post("/api/alerts/999/acknowledge"), 404, "does not exist")


class TestHistoryEndpoints(ApiTestCase):
    def add_three_analyses(self):
        machine = self.make_machine("PUMP-01")
        other = self.make_machine("PUMP-02")
        self.use_predictor(FixedPredictor("Normal", 0.1))
        self.upload(machine["id"], make_wav_bytes(seed=1), "one.wav")
        self.upload(other["id"], make_wav_bytes(seed=2), "two.wav")
        self.use_predictor(FixedPredictor("Potentially Abnormal", 0.9))
        self.upload(machine["id"], make_wav_bytes(seed=3), "three.wav")
        return machine, other

    def test_empty_history(self):
        page = self.client.get("/api/analyses").json()
        self.assertEqual(page, {"total": 0, "items": []})

    def test_history_is_newest_first_and_paged(self):
        self.add_three_analyses()
        page = self.client.get("/api/analyses").json()
        self.assertEqual(page["total"], 3)
        self.assertEqual([a["filename"] for a in page["items"]], ["three.wav", "two.wav", "one.wav"])
        small = self.client.get("/api/analyses?limit=2&offset=1").json()
        self.assertEqual(small["total"], 3)
        self.assertEqual([a["filename"] for a in small["items"]], ["two.wav", "one.wav"])

    def test_filters(self):
        machine, other = self.add_three_analyses()
        by_machine = self.client.get(f"/api/analyses?machine_pk={machine['id']}").json()
        self.assertEqual(by_machine["total"], 2)
        by_label = self.client.get("/api/analyses", params={"prediction": "Potentially Abnormal"}).json()
        self.assertEqual([a["filename"] for a in by_label["items"]], ["three.wav"])
        both = self.client.get(
            "/api/analyses", params={"machine_pk": other["id"], "prediction": "Potentially Abnormal"}).json()
        self.assertEqual(both["total"], 0)
        self.assertEqual(self.client.get("/api/analyses?date_from=2000-01-01").json()["total"], 3)
        self.assertEqual(self.client.get("/api/analyses?date_to=2000-01-01").json()["total"], 0)

    def test_bad_filters(self):
        self.assert_error(self.client.get("/api/analyses?prediction=Broken"), 422, "Prediction must be")
        self.assertEqual(self.client.get("/api/analyses?date_from=not-a-date").status_code, 422)
        self.assertEqual(self.client.get("/api/analyses?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/api/analyses?limit=100000").status_code, 422)
        self.assertEqual(self.client.get("/api/analyses?offset=-1").status_code, 422)

    def test_single_analysis(self):
        self.add_three_analyses()
        first = self.client.get("/api/analyses").json()["items"][0]
        found = self.client.get(f"/api/analyses/{first['id']}")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["filename"], "three.wav")
        self.assert_error(self.client.get("/api/analyses/999"), 404, "does not exist")

    def test_stats_after_uploads(self):
        self.add_three_analyses()
        stats = self.stats()
        self.assertEqual(stats["total_machines"], 2)
        self.assertEqual(stats["total_analyses"], 3)
        self.assertEqual(stats["normal_count"], 2)
        self.assertEqual(stats["abnormal_count"], 1)
        self.assertEqual(stats["total_alerts"], 1)


if __name__ == "__main__":
    unittest.main()
