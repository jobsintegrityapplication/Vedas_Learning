from __future__ import annotations

import io
import subprocess
import wave
from dataclasses import asdict, dataclass

from app.services.audio_validation import AudioInspection, inspect_audio


TARGET_WIDTH = 2


@dataclass
class PreprocessedAudio:
    data: bytes
    content_type: str
    status: str
    operations: list[str]
    inspection: AudioInspection

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload.pop("data")
        payload["inspection"] = self.inspection.as_dict()
        return payload


def _read_wav_format(data: bytes) -> tuple[int, int, int] | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as src:
            return src.getnchannels(), src.getsampwidth(), src.getframerate()
    except (wave.Error, EOFError):
        return None


def preprocess_audio(data: bytes, filename: str, content_type: str) -> PreprocessedAudio:
    """Decode accepted containers to mono PCM16 at the configured model rate.

    Conversion uses FFmpeg without a shell or temporary input file. If decoding
    is unavailable, no undecoded bytes are passed to a model.
    """
    from app.core.config import get_settings

    settings = get_settings()
    inspection = inspect_audio(data, filename, content_type)
    target_rate = settings.audio_sample_rate
    operations = ["validated_container"]
    wav_format = _read_wav_format(data) if inspection.container == "wav" else None
    if wav_format == (1, TARGET_WIDTH, target_rate):
        operations.append("already_model_compatible_pcm_wav")
        return PreprocessedAudio(data, "audio/wav", "normalized", operations, inspection)

    operations.append("decode_resample_mono_pcm16")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", "pipe:0", "-ac", "1", "-ar", str(target_rate),
                "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
            ],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        operations.append(f"decode_unavailable_{type(exc).__name__}")
        return PreprocessedAudio(b"", "audio/wav", "unavailable", operations, inspection)

    if result.returncode != 0 or not result.stdout:
        operations.append("decode_failed")
        return PreprocessedAudio(b"", "audio/wav", "unavailable", operations, inspection)

    # FFmpeg cannot seek back to finalize a WAV header on stdout. Its streaming
    # WAV header advertises an enormous placeholder frame count, so emit raw PCM
    # from FFmpeg and wrap it here with a correct seekable WAV header.
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as normalized_wav:
        normalized_wav.setnchannels(1)
        normalized_wav.setsampwidth(TARGET_WIDTH)
        normalized_wav.setframerate(target_rate)
        normalized_wav.writeframes(result.stdout)
    normalized_bytes = wav_buffer.getvalue()
    normalized = inspect_audio(normalized_bytes, "audio.wav", "audio/wav")
    if (normalized.sample_rate, normalized.channels, normalized.sample_width) != (target_rate, 1, TARGET_WIDTH):
        operations.append("normalization_validation_failed")
        return PreprocessedAudio(b"", "audio/wav", "unavailable", operations, inspection)
    operations.append("rewritten_pcm_wav")
    return PreprocessedAudio(normalized_bytes, "audio/wav", "normalized", operations, normalized)
