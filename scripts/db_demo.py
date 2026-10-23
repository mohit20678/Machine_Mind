"""Try the database from the terminal and see that data survives a restart.

Usage (Git Bash, venv active):
    python scripts/db_demo.py

Every run adds ONE placeholder analysis (marked MOCK) to a separate practice
database, data/db_demo.db. Your real database (data/machinemind.db) is not touched.
The result is NOT a real AI prediction.
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from database import models  # noqa: E402
from database.db import init_db  # noqa: E402

DEMO_MACHINE_ID = "DEMO-PUMP-00"


def main():
    parser = argparse.ArgumentParser(description="Database practice run.")
    parser.add_argument("--db", default=str(PROJECT_ROOT / "data" / "db_demo.db"))
    args = parser.parse_args()

    db_path = Path(args.db)
    existed_before = db_path.exists()
    init_db(db_path)
    print(f"Database file : {db_path}")
    print("Status        : " + ("already existed (data from earlier runs is kept)"
                                 if existed_before else "created now"))

    machine = models.get_machine_by_code(DEMO_MACHINE_ID, db_path=db_path)
    if machine is None:
        machine = models.create_machine(
            DEMO_MACHINE_ID, "Demo pump (practice only)", "Pump", "Practice data",
            db_path=db_path)
        print(f"Machine       : created {DEMO_MACHINE_ID}")
    else:
        print(f"Machine       : {DEMO_MACHINE_ID} already exists")

    total_before = models.count_analyses(db_path=db_path)
    result = models.save_analysis(
        machine["id"], f"practice_clip_{total_before + 1}.wav", "Normal", 0.0,
        model_name="mock-placeholder", model_version="0", is_mock=True,
        threshold=None, duration_seconds=10.0, sample_rate=16000, channels=8,
        db_path=db_path)
    print(f"Saved         : analysis #{result['analysis']['id']} "
          f"({result['analysis']['filename']}) - MOCK placeholder, not a real prediction")

    stats = models.get_dashboard_stats(db_path=db_path)
    print("\nTOTALS IN THIS DATABASE")
    print(f"  Machines          : {stats['total_machines']}")
    print(f"  Analyses          : {stats['total_analyses']}  "
          f"({stats['mock_analyses']} of them MOCK)")
    print(f"  Alerts            : {stats['total_alerts']}")

    print("\nLATEST ANALYSES (newest first)")
    for row in models.list_analyses(limit=5, db_path=db_path):
        kind = "MOCK" if row["is_mock"] else "REAL"
        print(f"  #{row['id']:<3} {row['created_at']}  {row['machine_code']:<13} "
              f"{row['prediction_label']:<21} {kind}  {row['filename']}")
    print("\nRun this script again: the totals go up by one, so the data was kept.")


if __name__ == "__main__":
    main()
