from app.services.engines.base import (
    EngineContext,
    PronunciationResult,
    SvaraResult,
    TranscriptResult,
    UNAVAILABLE_ASR,
    UNAVAILABLE_PRONUNCIATION,
    UNAVAILABLE_SVARA,
)


class NoneTranscriptionEngine:
    engine_id = "none"
    version = "0"

    def transcribe(self, context: EngineContext) -> TranscriptResult:
        return TranscriptResult(status="unavailable", reason=UNAVAILABLE_ASR, source=None)



class NonePronunciationEngine:
    engine_id = "none"
    version = "0"

    def evaluate(self, context: EngineContext, hypothesis_tokens: list[str] | None) -> PronunciationResult:
        reason = UNAVAILABLE_PRONUNCIATION
        if context.guru_audio is None:
            reason = (
                "Guru reference audio is not stored for this lesson, and no acoustic pronunciation engine is configured. "
                + UNAVAILABLE_PRONUNCIATION
            )
        return PronunciationResult(status="unavailable", reason=reason, scores=None)


class NoneSvaraEngine:
    engine_id = "none"
    version = "0"

    def evaluate(self, context: EngineContext) -> SvaraResult:
        return SvaraResult(status="unavailable", reason=UNAVAILABLE_SVARA, engine_id="none")


class NoneAlignmentEngine:
    engine_id = "none"
    version = "0"

    def forced_align(self, context: EngineContext, reference_tokens: list[str]) -> dict:
        return {"status": "unavailable", "reason": "No known-text alignment provider is configured.", "words": []}
