from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.services.engines.base import (
    EngineContext,
    PronunciationResult,
    TranscriptResult,
    UNAVAILABLE_PRONUNCIATION,
)
from app.services.engines.none import NoneTranscriptionEngine


class ScriptedTranscriptionEngine(NoneTranscriptionEngine):
    """Loads declared hypothesis tokens for sample recordings.

    This is not acoustic ASR. Results are evidence only when a fixture names the tokens.
    """

    engine_id = "scripted"
    version = "1"

    def transcribe(self, context: EngineContext) -> TranscriptResult:
        fixture = _load_fixture(context.learner_filename)
        if fixture is None:
            return TranscriptResult(
                status="unavailable",
                reason="No scripted transcript fixture is declared for this recording.",
                source="scripted_fixture",
            )
        tokens = fixture.get("tokens")
        if not isinstance(tokens, list) or not all(isinstance(item, str) for item in tokens):
            return TranscriptResult(
                status="unavailable",
                reason="Scripted fixture is present but does not declare a token list.",
                source="scripted_fixture",
            )
        return TranscriptResult(
            status="completed",
            reason="Hypothesis tokens loaded from a declared scripted fixture; this is not acoustic ASR.",
            tokens=tokens,
            source="scripted_fixture",
        )

class ScriptedPronunciationEngine:
    """Fixture-only evaluator kept separate from the transcription provider."""

    engine_id = "scripted"
    version = "1"

    def evaluate(self, context: EngineContext, hypothesis_tokens: list[str] | None) -> PronunciationResult:
        fixture = _load_fixture(context.learner_filename) or {}
        mismatches = fixture.get("pronunciation_mismatches")
        if not mismatches:
            return PronunciationResult(status="unavailable", reason=UNAVAILABLE_PRONUNCIATION, scores=None)
        if context.guru_audio is None:
            return PronunciationResult(
                status="unavailable",
                reason="Pronunciation evidence requires stored Guru reference audio in addition to a fixture.",
                scores=None,
            )
        return PronunciationResult(
            status="completed",
            reason="Pronunciation mismatches were declared in a scripted fixture, not estimated as a numeric score.",
            mismatches=list(mismatches),
            scores=None,
        )


def _load_fixture(filename: str) -> dict | None:
    settings = get_settings()
    directory = Path(settings.evaluation_fixture_dir or "")
    if not directory.is_dir():
        return None
    stem = Path(filename).stem
    path = directory / f"{stem}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None
