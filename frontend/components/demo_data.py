"""Demonstration data. Everything here is FAKE and must always be labeled as demo."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

ANALYSIS_COLUMNS = ["timestamp", "machine_id", "filename", "prediction", "demo_score"]
ALERT_COLUMNS = ["timestamp", "machine_id", "demo_score", "message"]
MACHINE_COLUMNS = ["machine_id", "name", "machine_type", "location"]


def empty_data():
    """What the dashboard shows when there is no real data yet."""
    analyses = pd.DataFrame(columns=ANALYSIS_COLUMNS)
    analyses["timestamp"] = pd.to_datetime(analyses["timestamp"])
    alerts = pd.DataFrame(columns=ALERT_COLUMNS)
    alerts["timestamp"] = pd.to_datetime(alerts["timestamp"])
    return pd.DataFrame(columns=MACHINE_COLUMNS), analyses, alerts


def get_demo_data():
    """Return (machines, analyses, alerts) with made-up values."""
    rng = np.random.default_rng(42)  # fixed seed: same fake data every time

    machines = pd.DataFrame(
        {
            "machine_id": ["DEMO-PUMP-00", "DEMO-PUMP-02", "DEMO-PUMP-04", "DEMO-PUMP-06"],
            "name": ["Demo Pump A", "Demo Pump B", "Demo Pump C", "Demo Pump D"],
            "machine_type": ["Pump"] * 4,
            "location": ["Demo Plant - Line 1", "Demo Plant - Line 1",
                         "Demo Plant - Line 2", "Demo Plant - Line 2"],
        }
    )

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    rows = []
    for number in range(60):
        timestamp = now - timedelta(hours=int(rng.integers(0, 14 * 24)))
        machine_id = machines["machine_id"].iloc[int(rng.integers(0, 4))]
        is_abnormal = rng.random() < 0.15
        score = rng.uniform(0.62, 0.95) if is_abnormal else rng.uniform(0.05, 0.50)
        rows.append(
            {
                "timestamp": timestamp,
                "machine_id": machine_id,
                "filename": f"demo_recording_{number:03d}.wav",
                "prediction": "Potentially Abnormal" if is_abnormal else "Normal",
                "demo_score": round(float(score), 3),
            }
        )

    analyses = pd.DataFrame(rows, columns=ANALYSIS_COLUMNS)
    analyses["timestamp"] = pd.to_datetime(analyses["timestamp"])
    analyses = analyses.sort_values("timestamp", ascending=False).reset_index(drop=True)

    alerts = analyses[analyses["prediction"] == "Potentially Abnormal"][
        ["timestamp", "machine_id", "demo_score"]
    ].copy()
    alerts["message"] = "Demo alert: recording flagged as potentially abnormal"
    alerts = alerts.reset_index(drop=True)

    return machines, analyses, alerts
