from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import get_settings

AUDIO_EXTENSIONS = {".m4a", ".wav", ".mp3", ".aac", ".ogg", ".webm"}

MAGIC = (
    (b"RIFF", "wav"),
    (b"OggS", "ogg"),
    (b"ID3", "mp3"),
    (b"fLaC", "flac"),
    (b"\x1aE\xdf\xa3", "webm"),
)


class AudioValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class AudioInspection:
    filename: str
    content_type: str
    byte_size: int
    container: str | None
    sample_rate: int | None = None
    channels: int | None = None
    sample_width: int | None = None
    duration_ms: int | None = None
    frame_count: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def sniff_container(data: bytes) -> str | None:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "mp4"
    for magic, name in MAGIC:
        if data.startswith(magic):
            return name
    if len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0:
        return "mp3"
    return None


def _parse_wav(data: bytes, inspection: AudioInspection) -> None:
    import io
    import wave

    with wave.open(io.BytesIO(data), "rb") as wav:
        inspection.channels = wav.getnchannels()
        inspection.sample_width = wav.getsampwidth()
        inspection.sample_rate = wav.getframerate()
        inspection.frame_count = wav.getnframes()
        if inspection.sample_rate:
            inspection.duration_ms = int(round(1000 * inspection.frame_count / inspection.sample_rate))


def inspect_audio(data: bytes, filename: str, content_type: str) -> AudioInspection:
    settings = get_settings()
    name = Path(filename or "audio.wav").name
    ext = Path(name).suffix.lower()
    if ext not in AUDIO_EXTENSIONS:
        raise AudioValidationError("Unsupported audio file")
    if not data:
        raise AudioValidationError("Empty audio file")
    if len(data) > settings.max_upload_bytes:
        raise AudioValidationError(f"Audio exceeds the {settings.max_upload_bytes} byte limit", 413)
    if len(data) < settings.min_audio_bytes:
        raise AudioValidationError("Audio file is too small to be a valid recording")
    container = sniff_container(data)
    if container is None:
        raise AudioValidationError("File contents are not a recognized audio container")
    inspection = AudioInspection(
        filename=name,
        content_type=content_type or "application/octet-stream",
        byte_size=len(data),
        container=container,
    )
    if container == "wav":
        try:
            _parse_wav(data, inspection)
        except Exception as exc:
            raise AudioValidationError("WAV header is invalid") from exc
        if not inspection.frame_count:
            raise AudioValidationError("WAV recording has no audio frames")
        if inspection.duration_ms is not None and inspection.duration_ms < settings.min_audio_duration_ms:
            raise AudioValidationError("Recording is shorter than the minimum allowed duration")
    return inspection
