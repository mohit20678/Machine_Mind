"""Audio validation and helper functions.

This file lives in backend/services so the FastAPI backend can reuse exactly the
same checks in Milestone 6. It does not depend on Streamlit.
"""
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

ALLOWED_EXTENSIONS = {".wav"}
MAX_FILE_SIZE_MB = 50
MIN_DURATION_SECONDS = 1.0
MAX_DURATION_SECONDS = 60.0
MIN_SAMPLE_RATE = 8000
MAX_CHANNELS = 16
SILENCE_PEAK_THRESHOLD = 1e-4


class AudioValidationError(Exception):
    """The recording was rejected. The message is written for the end user."""


@dataclass
class AudioInfo:
    filename: str
    size_bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    frames: int
    format_name: str
    subtype: str
    peak_amplitude: float
    rms: float
    is_silent: bool


def format_file_size(num_bytes):
    """Turn a byte count into a readable size such as '2.44 MB'."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def validate_audio(file_bytes, filename):
    """Check an uploaded recording and return (AudioInfo, samples).

    samples is a float32 NumPy array with shape (frames, channels), values -1 to 1.
    Raises AudioValidationError with a clear message if the file is not acceptable.
    """
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AudioValidationError(
            f"Unsupported file type '{extension or 'none'}'. Only WAV files are supported."
        )

    if len(file_bytes) == 0:
        raise AudioValidationError("The file is empty.")

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise AudioValidationError(
            f"The file is too large ({format_file_size(len(file_bytes))}). "
            f"The maximum size is {MAX_FILE_SIZE_MB} MB."
        )

    # Read only the header first. This is fast and tells us what the file really is.
    try:
        header = sf.info(io.BytesIO(file_bytes))
    except Exception as error:
        raise AudioValidationError(
            "The file could not be read as audio. It may be corrupted or may not be a real WAV file."
        ) from error

    if header.format != "WAV":
        raise AudioValidationError(
            f"The file content is '{header.format}', not WAV, even though the name ends in .wav."
        )
    if header.frames <= 0 or header.samplerate <= 0:
        raise AudioValidationError("The recording contains no audio samples.")
    if header.samplerate < MIN_SAMPLE_RATE:
        raise AudioValidationError(
            f"The sample rate ({header.samplerate} Hz) is too low. "
            f"The minimum is {MIN_SAMPLE_RATE} Hz."
        )
    if header.channels > MAX_CHANNELS:
        raise AudioValidationError(
            f"The recording has {header.channels} channels. The maximum is {MAX_CHANNELS}."
        )

    duration = header.frames / header.samplerate
    if duration < MIN_DURATION_SECONDS:
        raise AudioValidationError(
            f"The recording is too short ({duration:.2f} s). "
            f"The minimum length is {MIN_DURATION_SECONDS:.0f} second(s)."
        )
    if duration > MAX_DURATION_SECONDS:
        raise AudioValidationError(
            f"The recording is too long ({duration:.1f} s). "
            f"The maximum length is {MAX_DURATION_SECONDS:.0f} seconds."
        )

    # Now read the real samples.
    try:
        samples, sample_rate = sf.read(io.BytesIO(file_bytes), dtype="float32", always_2d=True)
    except Exception as error:
        raise AudioValidationError(
            "The audio data inside the file is damaged and could not be read."
        ) from error

    if not np.all(np.isfinite(samples)):
        raise AudioValidationError("The audio data contains invalid values (NaN or infinity).")

    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples))))

    info = AudioInfo(
        filename=filename,
        size_bytes=len(file_bytes),
        duration_seconds=duration,
        sample_rate=int(sample_rate),
        channels=int(samples.shape[1]),
        frames=int(samples.shape[0]),
        format_name=header.format,
        subtype=header.subtype,
        peak_amplitude=peak,
        rms=rms,
        is_silent=peak < SILENCE_PEAK_THRESHOLD,
    )
    return info, samples


def downsample_for_plot(signal, max_points=4000):
    """Shrink a long signal to a few thousand points so the chart stays fast.

    For each small block of samples we keep the lowest and highest value, so the
    shape of the waveform (including short spikes) is preserved.
    Returns (sample_positions, values).
    """
    total = len(signal)
    if total <= max_points:
        return np.arange(total), signal

    bins = max_points // 2
    block = total // bins
    usable = bins * block
    blocks = signal[:usable].reshape(bins, block)
    lows = blocks.min(axis=1)
    highs = blocks.max(axis=1)

    centers = np.arange(bins) * block + block // 2
    positions = np.repeat(centers, 2)
    values = np.empty(bins * 2, dtype=signal.dtype)
    values[0::2] = lows
    values[1::2] = highs
    return positions, values


def make_playback_wav(samples, sample_rate):
    """Make a mono WAV (average of all channels) that a browser can play.

    Browsers often cannot play 8-channel WAV files, so this is for listening only.
    """
    mono = np.clip(samples.mean(axis=1), -1.0, 1.0)
    buffer = io.BytesIO()
    sf.write(buffer, mono, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()
