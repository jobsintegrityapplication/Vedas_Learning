from types import SimpleNamespace
from pathlib import Path

from app.services.engines.sanskrit_text import normalize_sanskrit_text
from app.workers.tasks import _development_candidate_tokens, _development_diagnostic_enabled, _development_guru_audio


def test_development_tokens_cover_full_shloka_and_strip_punctuation_only():
    lesson = SimpleNamespace(sanskrit_text="सत्येनोत्तभिता भूमिः ।\nसूर्येणोत्तभिता द्यौः ॥")
    assert _development_candidate_tokens(lesson) == ["सत्येनोत्तभिता", "भूमिः", "सूर्येणोत्तभिता", "द्यौः"]


def test_development_tokens_fail_closed_for_missing_or_empty_lesson():
    assert _development_candidate_tokens(None) == []
    assert _development_candidate_tokens(SimpleNamespace(sanskrit_text="")) == []
    assert normalize_sanskrit_text(" \n । ॥ ") == ""


def test_diagnostic_fallback_is_local_development_only():
    assert _development_diagnostic_enabled(SimpleNamespace(evaluation_test_mode=True, app_env="development"))
    assert not _development_diagnostic_enabled(SimpleNamespace(evaluation_test_mode=True, app_env="test"))
    assert not _development_diagnostic_enabled(SimpleNamespace(evaluation_test_mode=True, app_env="production"))
    assert not _development_diagnostic_enabled(SimpleNamespace(evaluation_test_mode=False, app_env="development"))


def test_local_guru_clip_is_resolved_only_from_configured_directory(tmp_path: Path):
    clip = tmp_path / "rigveda-01.ogg"
    clip.write_bytes(b"guru-audio")
    settings = SimpleNamespace(development_guru_reference_dir=str(tmp_path))
    assert _development_guru_audio(settings, SimpleNamespace(slug="rigveda-01")) == (
        b"guru-audio", "audio/ogg", "rigveda-01.ogg"
    )
    assert _development_guru_audio(settings, SimpleNamespace(slug="../../secret")) is None
    assert _development_guru_audio(SimpleNamespace(development_guru_reference_dir=""), SimpleNamespace(slug="rigveda-01")) is None
