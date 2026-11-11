from pathlib import Path

from app.core.config import get_settings
from app.services.engines.base import AlignmentEngine, PronunciationEngine, SvaraEngine, TranscriptionEngine
from app.services.engines.none import NoneAlignmentEngine, NonePronunciationEngine, NoneSvaraEngine, NoneTranscriptionEngine
from app.services.engines.scripted import ScriptedPronunciationEngine, ScriptedTranscriptionEngine


_TRANSCRIBERS = {
    "none": NoneTranscriptionEngine,
    "not_configured": NoneTranscriptionEngine,
    "scripted": ScriptedTranscriptionEngine,
}

_SVARA = {
    "none": NoneSvaraEngine,
    "not_configured": NoneSvaraEngine,
}

_PRONUNCIATION = {
    "none": NonePronunciationEngine,
    "not_configured": NonePronunciationEngine,
    "scripted": ScriptedPronunciationEngine,
}

_ALIGNERS = {
    "none": NoneAlignmentEngine,
    "not_configured": NoneAlignmentEngine,
}


def _sushrota_model_available() -> bool:
    settings = get_settings()
    model_dir = Path(settings.sanskrit_asr_model_dir) if settings.sanskrit_asr_model_dir else None
    return bool(
        settings.sanskrit_asr_enabled
        and settings.audio_sample_rate == 16000
        and model_dir is not None
        and all((model_dir / name).is_file() for name in (
            "preprocessor.onnx", "sushrota_sanskrit_ctc_int8.onnx", "sanskrit_vocab.json"
        ))
    )


def _vedic_aligner_available() -> bool:
    settings = get_settings()
    return bool(
        settings.audio_sample_rate == 16000
        and settings.sanskrit_aligner_model_path
        and settings.sanskrit_aligner_vocab_path
        and Path(settings.sanskrit_aligner_model_path).is_file()
        and Path(settings.sanskrit_aligner_vocab_path).is_file()
    )


def get_transcription_engine() -> TranscriptionEngine:
    settings = get_settings()
    engine_id = (settings.evaluation_engine or "none").lower()
    if engine_id == "sushrota_onnx":
        if not _sushrota_model_available():
            return NoneTranscriptionEngine()
        from app.services.engines.sushrota_onnx import SushrotaOnnxTranscriptionEngine

        return SushrotaOnnxTranscriptionEngine()
    cls = _TRANSCRIBERS.get(engine_id, NoneTranscriptionEngine)
    return cls()


def get_alignment_engine() -> AlignmentEngine:
    settings = get_settings()
    engine_id = (settings.alignment_engine or "none").lower()
    if engine_id == "wav2vec2_vedic_onnx":
        if not _vedic_aligner_available():
            return NoneAlignmentEngine()
        from app.services.engines.vedic_onnx_aligner import VedicWav2Vec2OnnxAligner

        return VedicWav2Vec2OnnxAligner()
    cls = _ALIGNERS.get(engine_id, NoneAlignmentEngine)
    return cls()


def get_pronunciation_engine() -> PronunciationEngine:
    settings = get_settings()
    engine_id = (settings.pronunciation_engine or "none").lower()
    if not settings.pronunciation_evaluation_enabled:
        return NonePronunciationEngine()
    cls = _PRONUNCIATION.get(engine_id, NonePronunciationEngine)
    provider = cls()
    if settings.pronunciation_engine_version and settings.pronunciation_engine_version != "0":
        provider.version = settings.pronunciation_engine_version
    return provider


def get_svara_engine() -> SvaraEngine:
    settings = get_settings()
    engine_id = (settings.svara_engine or "none").lower()
    cls = _SVARA.get(engine_id, NoneSvaraEngine)
    return cls()


def engine_is_configured() -> bool:
    settings = get_settings()
    engine_id = (settings.evaluation_engine or "none").lower()
    if engine_id == "sushrota_onnx":
        return _sushrota_model_available()
    return engine_id in _TRANSCRIBERS and engine_id not in {"", "none", "not_configured"}


def alignment_engine_is_configured() -> bool:
    settings = get_settings()
    if (settings.alignment_engine or "none").lower() != "wav2vec2_vedic_onnx":
        return False
    return _vedic_aligner_available()


def pronunciation_engine_is_configured() -> bool:
    settings = get_settings()
    engine_id = (settings.pronunciation_engine or "none").lower()
    return settings.pronunciation_evaluation_enabled and engine_id in _PRONUNCIATION and engine_id not in {"", "none", "not_configured"}
