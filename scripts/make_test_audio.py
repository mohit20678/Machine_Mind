"""Create small WAV files (and some deliberately bad files) for testing the upload page.

Usage:  python scripts/make_test_audio.py
Output: data/test_audio/
"""
from pathlib import Path

import numpy as np
import soundfile as sf

OUT_DIR = Path("data/test_audio")
OUT_DIR.mkdir(parents=True, exist_ok=True)

RATE = 16000
rng = np.random.default_rng(0)


def tone(seconds, frequency):
    t = np.arange(int(seconds * RATE)) / RATE
    return 0.4 * np.sin(2 * np.pi * frequency * t)


def noise(seconds, level=0.02):
    return level * rng.standard_normal(int(seconds * RATE))


# Good files
sf.write(OUT_DIR / "valid_mono_16k.wav", tone(5, 220) + noise(5), RATE)

eight_channels = np.stack([tone(10, 100 + 40 * i) + noise(10) for i in range(8)], axis=1)
sf.write(OUT_DIR / "valid_8ch_16k.wav", eight_channels, RATE)

# Valid file that should give a warning
sf.write(OUT_DIR / "silent.wav", np.zeros(3 * RATE), RATE)

# Files that must be rejected
sf.write(OUT_DIR / "too_short.wav", tone(0.2, 220), RATE)
(OUT_DIR / "fake_audio.wav").write_text("this is not audio, only text", encoding="utf-8")
(OUT_DIR / "empty.wav").write_bytes(b"")

print("Created these files in", OUT_DIR)
for path in sorted(OUT_DIR.iterdir()):
    print(f"  {path.name}  ({path.stat().st_size} bytes)")
