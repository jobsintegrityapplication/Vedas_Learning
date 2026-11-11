import io
import struct
import tempfile
import wave
from pathlib import Path
import os
import shutil

# Keep generated audio outside the checkout so tests also run from read-only source trees.
FIXTURE_DIR = Path(tempfile.gettempdir()) / f"veda_learning_audio_tests_{os.getpid()}"
SOURCE_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "audio"


def make_wav_bytes(duration_ms: int = 200, sample_rate: int = 16000, freq: int = 440) -> bytes:
    frame_count = max(1, int(sample_rate * duration_ms / 1000))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            sample = int(8000 * ((index % 40) / 20 - 1))
            frames.extend(struct.pack("<h", sample))
        wav.writeframes(bytes(frames))
    return buf.getvalue()


def write_sample_recordings() -> dict[str, Path]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fixture in SOURCE_FIXTURE_DIR.glob("*.json"):
        shutil.copyfile(fixture, FIXTURE_DIR / fixture.name)
    paths = {}
    for name, duration in {
        "complete.wav": 240,
        "omission.wav": 180,
        "substitution.wav": 180,
        "pronunciation.wav": 240,
        "guru_reference.wav": 300,
    }.items():
        path = FIXTURE_DIR / name
        path.write_bytes(make_wav_bytes(duration_ms=duration))
        paths[name] = path
    return paths
