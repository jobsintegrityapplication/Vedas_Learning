from app.core.config import get_settings
from app.services.engines.registry import (
    alignment_engine_is_configured,
    engine_is_configured,
    get_pronunciation_engine,
    get_transcription_engine,
)


def test_sushrota_engine_stays_disabled_without_model_files(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALUATION_ENGINE", "sushrota_onnx")
    monkeypatch.setenv("SANSKRIT_ASR_ENABLED", "true")
    monkeypatch.setenv("SANSKRIT_ASR_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("AUDIO_SAMPLE_RATE", "16000")
    get_settings.cache_clear()
    try:
        assert engine_is_configured() is False
        assert get_transcription_engine().engine_id == "none"
    finally:
        get_settings.cache_clear()


def test_vedic_aligner_stays_disabled_without_local_checkpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("ALIGNMENT_ENGINE", "wav2vec2_vedic_onnx")
    monkeypatch.setenv("SANSKRIT_ALIGNER_MODEL_PATH", str(tmp_path / "model.int8.onnx"))
    monkeypatch.setenv("SANSKRIT_ALIGNER_VOCAB_PATH", str(tmp_path / "vocab.json"))
    get_settings.cache_clear()
    try:
        assert alignment_engine_is_configured() is False
    finally:
        get_settings.cache_clear()


def test_pronunciation_provider_is_independently_configured_from_asr(monkeypatch):
    monkeypatch.setenv("EVALUATION_ENGINE", "sushrota_onnx")
    monkeypatch.setenv("SANSKRIT_ASR_ENABLED", "false")
    monkeypatch.setenv("PRONUNCIATION_ENGINE", "scripted")
    monkeypatch.setenv("PRONUNCIATION_EVALUATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        assert get_transcription_engine().engine_id == "none"
        assert get_pronunciation_engine().engine_id == "scripted"

        monkeypatch.setenv("PRONUNCIATION_EVALUATION_ENABLED", "false")
        get_settings.cache_clear()
        assert get_pronunciation_engine().engine_id == "none"
    finally:
        get_settings.cache_clear()
