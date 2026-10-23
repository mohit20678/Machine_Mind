"""Software tests for the MachineMind database layer.

These tests use a temporary database file, so your real data is never touched.
They check the software only. They say nothing about how good the ML model is.

Run with:  pytest -v
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from database import models
from database.db import connect, get_db_path, init_db


class DatabaseTestCase(unittest.TestCase):
    """Gives every test its own empty temporary database."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.db = Path(self._folder.name) / "test.db"
        init_db(self.db)

    def make_machine(self, code="PUMP-01", name="Test pump", machine_type="Pump", location=None):
        return models.create_machine(code, name, machine_type, location, db_path=self.db)

    def save(self, machine_pk, label="Normal", score=0.2, alert_message=None, is_mock=True,
             filename="clip.wav"):
        return models.save_analysis(
            machine_pk, filename, label, score,
            model_name="test-model", model_version="0", is_mock=is_mock,
            threshold=0.5, duration_seconds=10.0, sample_rate=16000, channels=8,
            alert_message=alert_message, db_path=self.db,
        )


class TestInitialisation(DatabaseTestCase):
    def test_tables_are_created(self):
        with connect(self.db) as connection:
            names = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"machines", "analyses", "alerts"} <= names)

    def test_init_twice_keeps_data(self):
        self.make_machine()
        init_db(self.db)
        self.assertEqual(len(models.list_machines(db_path=self.db)), 1)

    def test_init_creates_missing_folder_and_file(self):
        nested = Path(self._folder.name) / "new_folder" / "fresh.db"
        init_db(nested)
        self.assertTrue(nested.exists())

    def test_db_path_can_be_set_by_environment_variable(self):
        with mock.patch.dict(os.environ, {"MACHINEMIND_DB_PATH": str(self.db)}):
            self.assertEqual(get_db_path(), self.db)

    def test_foreign_keys_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with connect(self.db) as connection:
                connection.execute(
                    "INSERT INTO analyses (machine_pk, filename, prediction_label, "
                    "anomaly_score, model_name, model_version, is_mock, created_at) "
                    "VALUES (999, 'x.wav', 'Normal', 0.1, 'm', '1', 0, 'now')")


class TestEmptyDatabase(DatabaseTestCase):
    def test_lists_are_empty(self):
        self.assertEqual(models.list_machines(db_path=self.db), [])
        self.assertEqual(models.list_analyses(db_path=self.db), [])
        self.assertEqual(models.list_alerts(db_path=self.db), [])
        self.assertEqual(models.count_analyses(db_path=self.db), 0)

    def test_stats_are_all_zero(self):
        stats = models.get_dashboard_stats(db_path=self.db)
        self.assertEqual(stats["total_machines"], 0)
        self.assertEqual(stats["total_analyses"], 0)
        self.assertEqual(stats["normal_count"], 0)
        self.assertEqual(stats["abnormal_count"], 0)
        self.assertEqual(stats["total_alerts"], 0)
        self.assertIsNone(stats["latest_analysis_at"])

    def test_missing_records_return_none(self):
        self.assertIsNone(models.get_machine(123, db_path=self.db))
        self.assertIsNone(models.get_machine_by_code("NOPE", db_path=self.db))
        self.assertIsNone(models.get_analysis(123, db_path=self.db))


class TestMachines(DatabaseTestCase):
    def test_create_and_read(self):
        machine = self.make_machine("PUMP-01", "Cooling pump", "Pump", "Plant 1")
        self.assertEqual(machine["machine_id"], "PUMP-01")
        self.assertEqual(machine["location"], "Plant 1")
        self.assertEqual(machine["analysis_count"], 0)
        self.assertEqual(models.get_machine(machine["id"], db_path=self.db)["name"], "Cooling pump")
        self.assertEqual(
            models.get_machine_by_code("pump-01", db_path=self.db)["id"], machine["id"])

    def test_optional_location_can_be_empty(self):
        self.assertIsNone(self.make_machine(location="   ")["location"])

    def test_duplicate_id_rejected_ignoring_case(self):
        self.make_machine("PUMP-01")
        with self.assertRaises(models.DuplicateError):
            self.make_machine("pump-01")
        self.assertEqual(len(models.list_machines(db_path=self.db)), 1)

    def test_invalid_input_rejected(self):
        bad_cases = [
            ("", "Name", "Pump"),
            ("PUMP 01", "Name", "Pump"),
            ("-PUMP", "Name", "Pump"),
            ("A" * 51, "Name", "Pump"),
            ("PUMP-01", "", "Pump"),
            ("PUMP-01", "   ", "Pump"),
            ("PUMP-01", "N" * 101, "Pump"),
            ("PUMP-01", "Name", ""),
            (None, "Name", "Pump"),
        ]
        for code, name, kind in bad_cases:
            with self.subTest(code=code, name=name, kind=kind):
                with self.assertRaises(models.InvalidDataError):
                    models.create_machine(code, name, kind, db_path=self.db)
        self.assertEqual(models.list_machines(db_path=self.db), [])

    def test_quotes_and_sql_text_are_stored_as_plain_text(self):
        tricky = "O'Brien \"pump\"; DROP TABLE machines;--"
        machine = self.make_machine("PUMP-01", tricky, "Pump")
        self.assertEqual(machine["name"], tricky)
        self.assertEqual(len(models.list_machines(db_path=self.db)), 1)

    def test_list_is_sorted_by_machine_id(self):
        for code in ("PUMP-03", "PUMP-01", "pump-02"):
            self.make_machine(code)
        codes = [m["machine_id"] for m in models.list_machines(db_path=self.db)]
        self.assertEqual(codes, ["PUMP-01", "pump-02", "PUMP-03"])

    def test_update_changes_fields_but_not_id(self):
        machine = self.make_machine("PUMP-01", "Old name", "Pump")
        updated = models.update_machine(
            machine["id"], "New name", "Fan", "Plant 2", db_path=self.db)
        self.assertEqual(updated["name"], "New name")
        self.assertEqual(updated["machine_type"], "Fan")
        self.assertEqual(updated["machine_id"], "PUMP-01")

    def test_update_missing_machine(self):
        with self.assertRaises(models.NotFoundError):
            models.update_machine(999, "Name", "Pump", db_path=self.db)

    def test_delete_machine(self):
        machine = self.make_machine()
        models.delete_machine(machine["id"], db_path=self.db)
        self.assertEqual(models.list_machines(db_path=self.db), [])

    def test_delete_missing_machine(self):
        with self.assertRaises(models.NotFoundError):
            models.delete_machine(999, db_path=self.db)

    def test_cannot_delete_machine_with_analyses(self):
        machine = self.make_machine()
        self.save(machine["id"])
        with self.assertRaises(models.InUseError):
            models.delete_machine(machine["id"], db_path=self.db)
        self.assertEqual(len(models.list_machines(db_path=self.db)), 1)
        self.assertEqual(models.get_machine(machine["id"], db_path=self.db)["analysis_count"], 1)


class TestAnalysesAndAlerts(DatabaseTestCase):
    def test_save_normal_analysis_without_alert(self):
        machine = self.make_machine()
        result = self.save(machine["id"], "Normal", 0.1)
        analysis = result["analysis"]
        self.assertIsNone(result["alert"])
        self.assertIsNone(analysis["alert_id"])
        self.assertEqual(analysis["machine_code"], "PUMP-01")
        self.assertEqual(analysis["prediction_label"], "Normal")
        self.assertEqual(analysis["anomaly_score"], 0.1)
        self.assertEqual(analysis["is_mock"], 1)
        self.assertEqual(analysis["channels"], 8)
        self.assertTrue(analysis["created_at"])

    def test_save_abnormal_analysis_with_alert(self):
        machine = self.make_machine()
        result = self.save(machine["id"], "Potentially Abnormal", 0.9, "Score above threshold")
        self.assertIsNotNone(result["alert"])
        self.assertEqual(result["alert"]["analysis_id"], result["analysis"]["id"])
        self.assertEqual(result["alert"]["machine_pk"], machine["id"])
        self.assertEqual(result["alert"]["acknowledged"], 0)
        self.assertEqual(result["analysis"]["alert_id"], result["alert"]["id"])

    def test_real_and_mock_results_are_kept_apart(self):
        machine = self.make_machine()
        self.save(machine["id"], is_mock=True)
        self.save(machine["id"], is_mock=False)
        self.assertEqual(models.get_dashboard_stats(db_path=self.db)["mock_analyses"], 1)

    def test_is_mock_must_be_explicit_true_or_false(self):
        machine = self.make_machine()
        with self.assertRaises(models.InvalidDataError):
            self.save(machine["id"], is_mock=1)
        with self.assertRaises(models.InvalidDataError):
            self.save(machine["id"], is_mock=None)

    def test_invalid_analysis_data_rejected_and_nothing_saved(self):
        machine = self.make_machine()
        pk = machine["id"]
        bad_calls = [
            dict(label="Broken"),
            dict(score=float("nan")),
            dict(score=float("inf")),
            dict(score="abc"),
            dict(score=None),
            dict(score=True),
            dict(filename="   "),
        ]
        for kwargs in bad_calls:
            with self.subTest(**{k: str(v) for k, v in kwargs.items()}):
                with self.assertRaises(models.InvalidDataError):
                    self.save(pk, **kwargs)
        with self.assertRaises(models.InvalidDataError):
            models.save_analysis(pk, "a.wav", "Normal", 0.1, model_name="m", model_version="1",
                                 is_mock=True, sample_rate=0, db_path=self.db)
        with self.assertRaises(models.InvalidDataError):
            models.save_analysis(pk, "a.wav", "Normal", 0.1, model_name="m", model_version="1",
                                 is_mock=True, channels=2.5, db_path=self.db)
        self.assertEqual(models.count_analyses(db_path=self.db), 0)

    def test_unknown_machine_rejected(self):
        with self.assertRaises(models.NotFoundError):
            self.save(999)
        self.assertEqual(models.count_analyses(db_path=self.db), 0)

    def test_analysis_and_alert_are_saved_together_or_not_at_all(self):
        machine = self.make_machine()
        with mock.patch.object(models, "_fetch_alert_for_analysis",
                               side_effect=RuntimeError("simulated crash")):
            with self.assertRaises(RuntimeError):
                self.save(machine["id"], "Potentially Abnormal", 0.9, "alert")
        self.assertEqual(models.count_analyses(db_path=self.db), 0)
        self.assertEqual(models.list_alerts(db_path=self.db), [])

    def test_one_alert_per_analysis_is_enforced_by_database(self):
        machine = self.make_machine()
        result = self.save(machine["id"], "Potentially Abnormal", 0.9, "alert")
        with self.assertRaises(sqlite3.IntegrityError):
            with connect(self.db) as connection:
                connection.execute(
                    "INSERT INTO alerts (analysis_id, machine_pk, message, acknowledged, "
                    "created_at) VALUES (?, ?, 'again', 0, 'now')",
                    (result["analysis"]["id"], machine["id"]))

    def test_get_analysis(self):
        machine = self.make_machine()
        saved = self.save(machine["id"])["analysis"]
        found = models.get_analysis(saved["id"], db_path=self.db)
        self.assertEqual(found["filename"], "clip.wav")
        self.assertEqual(found["machine_name"], "Test pump")

    def test_history_order_and_paging(self):
        machine = self.make_machine()
        for number in range(5):
            self.save(machine["id"], filename=f"clip{number}.wav")
        names = [a["filename"] for a in models.list_analyses(db_path=self.db)]
        self.assertEqual(names, [f"clip{n}.wav" for n in (4, 3, 2, 1, 0)])
        page = models.list_analyses(limit=2, offset=2, db_path=self.db)
        self.assertEqual([a["filename"] for a in page], ["clip2.wav", "clip1.wav"])
        self.assertEqual(models.count_analyses(db_path=self.db), 5)

    def test_filters(self):
        one = self.make_machine("PUMP-01")
        two = self.make_machine("PUMP-02")
        self.save(one["id"], "Normal", 0.1)
        self.save(one["id"], "Potentially Abnormal", 0.9, "alert")
        self.save(two["id"], "Normal", 0.2)
        list_ = lambda **kw: models.list_analyses(db_path=self.db, **kw)
        self.assertEqual(len(list_(machine_pk=one["id"])), 2)
        self.assertEqual(len(list_(prediction_label="Normal")), 2)
        self.assertEqual(len(list_(machine_pk=one["id"], prediction_label="Potentially Abnormal")), 1)
        self.assertEqual(models.count_analyses(machine_pk=two["id"], db_path=self.db), 1)

    def test_date_filters(self):
        machine = self.make_machine()
        self.save(machine["id"])
        with connect(self.db) as connection:
            connection.execute("UPDATE analyses SET created_at = '2020-01-15T10:00:00+00:00'")
        self.save(machine["id"], filename="new.wav")
        list_ = lambda **kw: models.list_analyses(db_path=self.db, **kw)
        self.assertEqual(len(list_(date_from="2020-01-01", date_to="2020-01-31")), 1)
        self.assertEqual(len(list_(date_from="2020-01-16")), 1)
        self.assertEqual(len(list_(date_to="2020-01-14")), 0)
        self.assertEqual(len(list_(date_from="2020-01-01")), 2)

    def test_bad_filters_rejected(self):
        with self.assertRaises(models.InvalidDataError):
            models.list_analyses(prediction_label="Broken", db_path=self.db)
        with self.assertRaises(models.InvalidDataError):
            models.list_analyses(date_from="not a date", db_path=self.db)
        with self.assertRaises(models.InvalidDataError):
            models.list_analyses(limit=0, db_path=self.db)
        with self.assertRaises(models.InvalidDataError):
            models.list_analyses(limit=100000, db_path=self.db)

    def test_filter_text_cannot_inject_sql(self):
        machine = self.make_machine()
        self.save(machine["id"])
        with self.assertRaises(models.InvalidDataError):
            models.list_analyses(prediction_label="Normal' OR '1'='1", db_path=self.db)
        self.assertEqual(models.count_analyses(db_path=self.db), 1)

    def test_alert_list_and_acknowledge(self):
        machine = self.make_machine()
        first = self.save(machine["id"], "Potentially Abnormal", 0.9, "alert one")["alert"]
        self.save(machine["id"], "Potentially Abnormal", 0.8, "alert two")
        self.assertEqual(len(models.list_alerts(db_path=self.db)), 2)
        updated = models.acknowledge_alert(first["id"], db_path=self.db)
        self.assertEqual(updated["acknowledged"], 1)
        open_alerts = models.list_alerts(only_unacknowledged=True, db_path=self.db)
        self.assertEqual([a["message"] for a in open_alerts], ["alert two"])
        self.assertEqual(len(models.list_alerts(machine_pk=machine["id"], db_path=self.db)), 2)
        self.assertEqual(models.get_dashboard_stats(db_path=self.db)["open_alerts"], 1)

    def test_acknowledge_missing_alert(self):
        with self.assertRaises(models.NotFoundError):
            models.acknowledge_alert(999, db_path=self.db)

    def test_dashboard_stats_count_everything(self):
        machine = self.make_machine()
        self.make_machine("PUMP-02")
        self.save(machine["id"], "Normal", 0.1)
        self.save(machine["id"], "Normal", 0.2)
        self.save(machine["id"], "Potentially Abnormal", 0.9, "alert")
        stats = models.get_dashboard_stats(db_path=self.db)
        self.assertEqual(stats["total_machines"], 2)
        self.assertEqual(stats["total_analyses"], 3)
        self.assertEqual(stats["normal_count"], 2)
        self.assertEqual(stats["abnormal_count"], 1)
        self.assertEqual(stats["total_alerts"], 1)
        self.assertIsNotNone(stats["latest_analysis_at"])

    def test_deleting_an_analysis_removes_its_alert(self):
        machine = self.make_machine()
        result = self.save(machine["id"], "Potentially Abnormal", 0.9, "alert")
        with connect(self.db) as connection:
            connection.execute("DELETE FROM analyses WHERE id = ?", (result["analysis"]["id"],))
        self.assertEqual(models.list_alerts(db_path=self.db), [])


class TestPersistence(DatabaseTestCase):
    def test_data_survives_a_restart(self):
        machine = self.make_machine("PUMP-01", "Persistent pump", "Pump")
        self.save(machine["id"], "Potentially Abnormal", 0.9, "alert")
        # A restart means: new connections, init_db runs again, same file on disk.
        init_db(self.db)
        self.assertEqual(models.list_machines(db_path=self.db)[0]["name"], "Persistent pump")
        self.assertEqual(models.count_analyses(db_path=self.db), 1)
        self.assertEqual(len(models.list_alerts(db_path=self.db)), 1)


if __name__ == "__main__":
    unittest.main()
