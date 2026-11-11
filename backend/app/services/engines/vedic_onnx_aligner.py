from __future__ import annotations

import io
import json
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.services.engines.base import EngineContext
from app.services.engines.ctc_alignment import AlignmentError, forced_align
from app.services.engines.sanskrit_text import normalize_sanskrit_text, sanskrit_aksharas


ENGINE_ID = "wav2vec2_vedic_onnx"
BLANK_ID = 0  # The checkpoint card documents <s> as the actual CTC blank.


def aligner_is_available() -> bool:
    settings = get_settings()
    return bool(
        settings.alignment_engine.lower() == ENGINE_ID
        and settings.audio_sample_rate == 16000
        and settings.sanskrit_aligner_model_path
        and settings.sanskrit_aligner_vocab_path
        and Path(settings.sanskrit_aligner_model_path).is_file()
        and Path(settings.sanskrit_aligner_vocab_path).is_file()
    )


@lru_cache(maxsize=2)
def _session(model_path: str, threads: int, requested_device: str):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    providers = ort.get_available_providers()
    if requested_device.lower() in {"cuda", "gpu"} and "CUDAExecutionProvider" in providers:
        selected = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    else:
        selected = ["CPUExecutionProvider"]
    session = ort.InferenceSession(model_path, sess_options=options, providers=selected)
    return session, session.get_providers()[0]


def _audio_signal(audio_bytes: bytes, sample_rate: int) -> np.ndarray:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != sample_rate:
            raise ValueError("Audio was not normalized to mono PCM16 at the configured sample rate")
        signal = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    # Wav2Vec2FeatureExtractor's default do_normalize=True.
    standard_deviation = float(signal.std())
    return (signal - float(signal.mean())) / max(standard_deviation, 1e-7)


class VedicWav2Vec2OnnxAligner:
    engine_id = ENGINE_ID
    version = "6d201fadeab60e1bcf037241106843a33a316636-int8"

    def forced_align(self, context: EngineContext, reference_tokens: list[str]) -> dict:
        settings = get_settings()
        if not aligner_is_available():
            return {"status": "unavailable", "reason": "Vedic aligner is disabled or its local ONNX/vocabulary files are unavailable.", "words": []}
        if context.learner_audio.status != "normalized" or not context.learner_audio.data:
            return {"status": "unavailable", "reason": "Learner audio could not be decoded to the aligner's required PCM format.", "words": []}
        try:
            session, execution_provider = _session(
                settings.sanskrit_aligner_model_path, settings.model_num_threads, settings.model_device
            )
            signal = _audio_signal(context.learner_audio.data, settings.audio_sample_rate)
            input_name = session.get_inputs()[0].name
            output_name = session.get_outputs()[0].name
            logits = session.run([output_name], {input_name: signal[np.newaxis, :].astype(np.float32)})[0][0]
            if logits.ndim != 2:
                raise ValueError("Aligner returned an unsupported CTC output shape")
            log_probs = logits - np.logaddexp.reduce(logits, axis=-1, keepdims=True)
            vocab_payload = json.loads(Path(settings.sanskrit_aligner_vocab_path).read_text(encoding="utf-8"))
            vocab = vocab_payload.get("vocab", vocab_payload) if isinstance(vocab_payload, dict) else vocab_payload
            if not isinstance(vocab, dict):
                raise ValueError("Aligner vocabulary must map Devanagari labels to CTC ids")

            words = [normalize_sanskrit_text(token) for token in reference_tokens]
            words = [word for word in words if word]
            if not words:
                raise ValueError("Reference has no alignable Sanskrit words")
            target_ids: list[int] = []
            target_units: list[tuple[int, str]] = []
            delimiter_id = vocab.get("|")
            if not isinstance(delimiter_id, int) or delimiter_id == BLANK_ID:
                raise ValueError("Aligner vocabulary is missing its CTC word delimiter")
            for word_index, word in enumerate(words):
                for char in word:
                    label_id = vocab.get(char)
                    if not isinstance(label_id, int) or label_id == BLANK_ID:
                        raise ValueError(f"Aligner vocabulary does not support reference character U+{ord(char):04X}")
                    target_ids.append(label_id)
                    target_units.append((word_index, char))
                if word_index < len(words) - 1:
                    target_ids.append(delimiter_id)
                    target_units.append((-1, "|"))

            state_path = forced_align(log_probs, target_ids, BLANK_ID)
            frames_by_target: dict[int, list[int]] = {index: [] for index in range(len(target_ids))}
            for frame, state in enumerate(state_path):
                if state % 2 == 1:
                    target_index = state // 2
                    frames_by_target[target_index].append(frame)
            duration_ms = len(signal) * 1000 / settings.audio_sample_rate
            frame_ms = duration_ms / logits.shape[0]
            char_rows = []
            for index, ((word_index, char), label_id) in enumerate(zip(target_units, target_ids)):
                frames = frames_by_target[index]
                if word_index < 0:
                    continue
                if not frames:
                    raise AlignmentError("A reference character received no CTC frames")
                posterior = float(np.exp(log_probs[frames, label_id]).mean())
                char_rows.append({
                    "word_index": word_index,
                    "char": char,
                    "start_ms": int(round(frames[0] * frame_ms)),
                    "end_ms": int(round((frames[-1] + 1) * frame_ms)),
                    "posterior": posterior,
                })

            word_rows = []
            akshara_rows = []
            for word_index, word in enumerate(words):
                char_rows_for_word = [item for item in char_rows if item["word_index"] == word_index]
                if len(char_rows_for_word) != len(word):
                    raise AlignmentError("Reference word character alignment is incomplete")
                char_cursor = 0
                clusters = sanskrit_aksharas(word)
                for cluster in clusters:
                    cluster_rows = char_rows_for_word[char_cursor:char_cursor + len(cluster)]
                    char_cursor += len(cluster)
                    akshara_rows.append({
                        "word_order": word_index + 1,
                        "word": word,
                        "akshara": cluster,
                        "start_ms": min(row["start_ms"] for row in cluster_rows),
                        "end_ms": max(row["end_ms"] for row in cluster_rows),
                        "mean_frame_posterior": round(sum(row["posterior"] for row in cluster_rows) / len(cluster_rows), 5),
                        "status": "aligned_candidate",
                    })
                start_ms = min(row["start_ms"] for row in char_rows_for_word)
                end_ms = max(row["end_ms"] for row in char_rows_for_word)
                mean_posterior = sum(row["posterior"] for row in char_rows_for_word) / len(char_rows_for_word)
                word_rows.append({
                    "word_order": word_index + 1,
                    "word": word,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "confidence": round(mean_posterior, 5),
                    "confidence_type": "mean_ctc_frame_posterior_uncalibrated",
                    "status": "aligned_candidate",
                })

            return {
                "status": "completed",
                "engine_id": self.engine_id,
                "engine_version": self.version,
                "execution_provider": execution_provider,
                "sample_rate_hz": settings.audio_sample_rate,
                "blank_id": BLANK_ID,
                "words": word_rows,
                "aksharas": akshara_rows,
                "interpretation": "Known-text CTC forced-fit timing candidate; timestamps and posteriors are not validated pronunciation scores.",
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "reason": f"Vedic known-text alignment failed ({type(exc).__name__}); no pronunciation score was produced.",
                "words": [],
            }
