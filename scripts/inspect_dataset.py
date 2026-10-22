"""Scan a machine-sound dataset folder and summarise what is really inside.

Usage (Git Bash, venv active):
    python scripts/inspect_dataset.py --path "C:/Users/ASUS/Desktop/MIMII"

The dataset path is never hardcoded. Pass --path or set DATASET_PATH in a .env file.
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

import soundfile as sf
from dotenv import load_dotenv

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg"}
KNOWN_MACHINE_TYPES = {"fan", "pump", "slider", "valve", "gearbox", "toycar", "toytrain", "bearing"}
ABNORMAL_WORDS = {"abnormal", "anomaly", "anomalous"}


def detect_label(dir_parts, filename):
    """Look for normal/abnormal in folder names first, then in the file name."""
    for part in dir_parts:
        word = part.lower()
        if word in ABNORMAL_WORDS:
            return "abnormal"
        if word == "normal":
            return "normal"
    name = filename.lower()
    if name.startswith(tuple(ABNORMAL_WORDS)):
        return "abnormal"
    if name.startswith("normal"):
        return "normal"
    return "unknown"


def detect_machine_type(names):
    """Look for a known machine word such as fan or pump in the folder names."""
    for name in names:
        for token in re.split(r"[_\-\s]+", name.lower()):
            if token in KNOWN_MACHINE_TYPES:
                return token
    return "unknown"


def detect_machine_id(dir_parts):
    """Look for folder names like id_00."""
    for part in dir_parts:
        match = re.match(r"^id[_\-]?(\d+)$", part.lower())
        if match:
            return "id_" + match.group(1)
    return "unknown"


def scan(root):
    rows = []
    other_extensions = Counter()
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            ext = Path(filename).suffix.lower()
            if ext not in AUDIO_EXTENSIONS:
                other_extensions[ext or "(no extension)"] += 1
                continue
            full_path = Path(dirpath) / filename
            relative = full_path.relative_to(root)
            dir_parts = list(relative.parts[:-1])
            rows.append(
                {
                    "relative_path": relative.as_posix(),
                    "filename": filename,
                    "machine_type": detect_machine_type([root.name] + dir_parts),
                    "machine_id": detect_machine_id(dir_parts),
                    "label": detect_label(dir_parts, filename),
                    "dir_parts": dir_parts,
                }
            )
    return rows, other_extensions


def build_summary(root, rows, other_extensions):
    lines = []
    lines.append("DATASET SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Scanned folder : {root}")
    lines.append(f"Audio files    : {len(rows)}")
    ext_counts = Counter(Path(r["filename"]).suffix.lower() for r in rows)
    lines.append(f"Audio types    : {dict(ext_counts)}")
    if other_extensions:
        lines.append(f"Other files    : {dict(other_extensions)}")
        if ".zip" in other_extensions:
            lines.append("WARNING: .zip files found. Extract them first, then scan again.")
    lines.append("")

    # Folder tree (first 3 levels) with audio file counts
    lines.append("FOLDER STRUCTURE (first 3 levels, audio file counts)")
    lines.append("-" * 60)
    tree = Counter()
    for row in rows:
        for depth in range(1, min(3, len(row["dir_parts"])) + 1):
            tree[tuple(row["dir_parts"][:depth])] += 1
    shown = 0
    for key in sorted(tree):
        lines.append("  " * (len(key) - 1) + f"{key[-1]}/  ({tree[key]} files)")
        shown += 1
        if shown >= 60:
            lines.append("  ... (more folders not shown)")
            break
    if not tree:
        lines.append("(audio files are directly inside the scanned folder)")
    lines.append("")

    # Labels
    lines.append("LABELS FOUND")
    lines.append("-" * 60)
    label_counts = Counter(r["label"] for r in rows)
    for label, count in sorted(label_counts.items()):
        lines.append(f"  {label}: {count}")
    if label_counts.get("unknown"):
        lines.append("  ('unknown' = no normal/abnormal word found in folder or file name)")
    lines.append("")

    # Machine type / ID / label table
    lines.append("MACHINE TYPE / MACHINE ID / LABEL")
    lines.append("-" * 60)
    group_counts = Counter((r["machine_type"], r["machine_id"], r["label"]) for r in rows)
    for (machine_type, machine_id, label), count in sorted(group_counts.items()):
        lines.append(f"  {machine_type:<10} {machine_id:<10} {label:<10} {count}")
    lines.append("")

    # Sample files
    lines.append("SAMPLE FILE NAMES (first 5)")
    lines.append("-" * 60)
    for row in rows[:5]:
        lines.append(f"  {row['relative_path']}")
    lines.append("")

    # Real audio details from the first file
    lines.append("FIRST AUDIO FILE DETAILS")
    lines.append("-" * 60)
    if rows:
        first = root / rows[0]["relative_path"]
        try:
            info = sf.info(str(first))
            lines.append(f"  File        : {rows[0]['relative_path']}")
            lines.append(f"  Sample rate : {info.samplerate} Hz")
            lines.append(f"  Channels    : {info.channels}")
            lines.append(f"  Duration    : {info.duration:.2f} s")
            lines.append(f"  Format      : {info.format} / {info.subtype}")
        except Exception as error:
            lines.append(f"  Could not read the file: {error}")
    return lines


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Scan a machine-sound dataset folder.")
    parser.add_argument("--path", default=os.environ.get("DATASET_PATH"), help="Dataset folder")
    parser.add_argument("--summary-out", default="docs/dataset_summary.txt")
    parser.add_argument("--csv-out", default="data/dataset_index.csv")
    args = parser.parse_args()

    if not args.path:
        print("ERROR: give the dataset folder with --path, or set DATASET_PATH in a .env file.")
        sys.exit(1)

    root = Path(args.path)
    if not root.is_dir():
        print(f"ERROR: folder not found: {root}")
        sys.exit(1)

    print(f"Scanning {root} ... (large datasets can take a minute)")
    rows, other_extensions = scan(root)

    if not rows:
        print("No audio files found. Check the path, and extract any .zip files first.")
        if other_extensions:
            print(f"Other files found: {dict(other_extensions)}")
        sys.exit(1)

    lines = build_summary(root, rows, other_extensions)
    print("\n".join(lines))

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    csv_path = Path(args.csv_out)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["relative_path", "filename", "machine_type", "machine_id", "label"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})

    print(f"\nSaved summary to {summary_path}")
    print(f"Saved file list to {csv_path}")


if __name__ == "__main__":
    main()
