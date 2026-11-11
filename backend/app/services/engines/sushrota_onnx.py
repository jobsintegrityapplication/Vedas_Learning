from __future__ import annotations

import io
import json
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.services.engines.base import (
    EngineContext,
    TranscriptResult,
)
from app.services.engines.none import NoneTranscriptionEngine
from app.services.engines.sanskrit_text import normalize_sanskrit_text


ENGINE_ID = "sushrota_onnx"
EXPECTED_FILES = ("preprocessor.onnx", "sushrota_sanskrit_ctc_int8.onnx", "sanskrit_vocab.json")


def configured_model_dir() -> Path | None:
    settings = get_settings()
    if not settings.sanskrit_asr_enabled or settings.audio_sample_rate != 16000 or not settings.sanskrit_asr_model_dir:
        return None
    directory = Path(settings.sanskrit_asr_model_dir)
    if not all((directory / filename).is_file() for filename in EXPECTED_FILES):
        return None
    return directory


@lru_cache(maxsize=2)
def _sessions(model_dir: str, threads: int):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    path = Path(model_dir)
    preprocessor = ort.InferenceSession(str(path / EXPECTED_FILES[0]), sess_options=options, providers=["CPUExecutionProvider"])
    model = ort.InferenceSession(str(path / EXPECTED_FILES[1]), sess_options=options, providers=["CPUExecutionProvider"])
    payload = json.loads((path / EXPECTED_FILES[2]).read_text(encoding="utf-8"))
    vocab = payload.get("vocab", payload) if isinstance(payload, dict) else payload
    if not isinstance(vocab, (dict, list)):
        raise ValueError("Suśrotā vocabulary has an unsupported shape")
    return preprocessor, model, vocab


def _wav_float32(audio_bytes: bytes, sample_rate: int) -> np.ndarray:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != sample_rate:
            raise ValueError("Audio was not normalized to mono PCM16 at the configured sample rate")
        signal = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32)
    return signal / 32768.0


def _vocab_token(vocab, token_id: int) -> str:
    if isinstance(vocab, list):
        return str(vocab[token_id]) if token_id < len(vocab) else ""
    return str(vocab.get(str(token_id), vocab.get(token_id, "")))


class SushrotaOnnxTranscriptionEngine(NoneTranscriptionEngine):
    engine_id = ENGINE_ID
    version = "v13b-onnx-int8"

    def transcribe(self, context: EngineContext) -> TranscriptResult:
        settings = get_settings()
        model_dir = configured_model_dir()
        if model_dir is None:
            return TranscriptResult(
                status="unavailable",
                reason="Suśrotā ASR is disabled or its local model files are unavailable.",
                source=ENGINE_ID,
            )
        if context.learner_audio.status != "normalized" or not context.learner_audio.data:
            return TranscriptResult(
                status="unavailable",
                reason="Learner audio could not be decoded to the model's required PCM format.",
                source=ENGINE_ID,
            )
        try:
            signal = _wav_float32(context.learner_audio.data, settings.audio_sample_rate)
            preprocessor, model, vocab = _sessions(str(model_dir), settings.model_num_threads)
            audio_signal = signal[np.newaxis, :].astype(np.float32)
            length = np.asarray([len(signal)], dtype=np.int64)
            features, feature_lengths = preprocessor.run(None, {"audio_signal": audio_signal, "length": length})
            logits = model.run(None, {"audio_signal": features, "length": feature_lengths})[0]
            if logits.ndim != 3 or logits.shape[0] != 1:
                raise ValueError("Suśrotā returned an unsupported CTC output shape")
            output: list[str] = []
            previous = -1
            for raw_id in np.argmax(logits[0], axis=-1):
                token_id = int(raw_id)
                if token_id != previous and token_id != 0:
                    output.append(_vocab_token(vocab, token_id))
                previous = token_id
            transcript = "".join(output).replace("▁", " ").strip()
            tokens = normalize_sanskrit_text(transcript).split()
            if not tokens:
                return TranscriptResult(status="unavailable", reason="Suśrotā returned no usable Sanskrit tokens.", source=ENGINE_ID)
            return TranscriptResult(
                status="completed",
                reason="Transcribed by the configured Suśrotā CTC model. Transcript agreement is not pronunciation accuracy.",
                tokens=tokens,
                source=ENGINE_ID,
                confidence_declared=False,
            )
        except Exception as exc:
            return TranscriptResult(
                status="unavailable",
                reason=f"Suśrotā inference failed ({type(exc).__name__}); no score was produced.",
                source=ENGINE_ID,
            )

