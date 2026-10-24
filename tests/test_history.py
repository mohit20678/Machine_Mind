from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from database import models
from database.db import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client whose database is a temporary file, never the real one."""
    monkeypatch.setenv("MACHINEMIND_DB_PATH", str(tmp_path / "api_test.db"))
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def add_analysis(machine_code, label="Normal", score=0.2):
    machine = models.get_machine_by_code(machine_code) or models.create_machine(
        machine_code, "Test machine", "Pump"
    )
    models.save_analysis(
        machine["id"], "clip.wav", label, score,
        model_name="test-model", model_version="0", is_mock=True,
    )


def test_empty_history(client):
    response = client.get("/history")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_history_returns_saved_analyses(client):
    add_analysis("PUMP-01")
    add_analysis("PUMP-01", label="Potentially Abnormal", score=0.9)
    body = client.get("/history").json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["is_mock"] is True
    assert "stored_path" not in body["items"][0]


def test_filter_by_machine(client):
    add_analysis("PUMP-01")
    add_analysis("FAN-01")
    body = client.get("/history", params={"machine_id": "PUMP-01"}).json()
    assert body["total"] == 1
    assert body["items"][0]["machine_code"] == "PUMP-01"


def test_unknown_machine_gives_404(client):
    response = client.get("/history", params={"machine_id": "NOPE-99"})
    assert response.status_code == 404


def test_invalid_prediction_gives_400(client):
    response = client.get("/history", params={"prediction": "Maybe Broken"})
    assert response.status_code == 400
    assert "Prediction must be one of" in response.json()["detail"]


def test_bad_date_gives_422(client):
    response = client.get("/history", params={"date_from": "not-a-date"})
    assert response.status_code == 422


def test_limit_too_large_gives_422(client):
    response = client.get("/history", params={"limit": 5000})
    assert response.status_code == 422


def test_filter_by_date(client):
    add_analysis("PUMP-01")
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    assert client.get("/history", params={"date_from": str(today)}).json()["total"] == 1
    assert client.get("/history", params={"date_from": str(tomorrow)}).json()["total"] == 0
