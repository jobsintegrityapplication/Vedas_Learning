from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.services.audio_preprocess import PreprocessedAudio


UNAVAILABLE_ASR = (
    "Word-level skipped/substituted analysis requires a validated Sanskrit ASR "
    "or forced-alignment engine using Guru reference audio as ground truth. "
    "No such engine is configured."
)
UNAVAILABLE_PRONUNCIATION = (
    "Pronunciation analysis requires a validated phonetic/acoustic provider and reviewed "
    "reference data for the learner-selected recitation profile. Voice similarity, speaker identity, "
    "and raw pitch matching are not used."
)
UNAVAILABLE_SVARA = (
    "Vedic svara evaluation is unavailable. A validated specialist svara engine has not been configured."
)


@dataclass
class TranscriptResult:
    status: str
    reason: str
    tokens: list[str] | None = None
    source: str | None = None
    confidence_declared: bool = False
    confidence: float | None = None
    token_confidences: list[float] | None = None
    evaluation_passed: bool | None = None


@dataclass
class PronunciationResult:
    status: str
    reason: str
    mismatches: list[dict] = field(default_factory=list)
    scores: dict | None = None
    confidence: float | None = None
    evidence: list[dict] = field(default_factory=list)
    correction_guidance: list[dict] = field(default_factory=list)


@dataclass
class SvaraResult:
    status: str
    reason: str
    engine_id: str = "none"
    evidence: dict | None = None
    confidence: float | None = None
    correction_guidance: list[dict] = field(default_factory=list)


@dataclass
class EngineContext:
    lesson_slug: str
    reference_tokens: list[str]
    learner_filename: str
    learner_audio: PreprocessedAudio
    guru_audio: PreprocessedAudio | None
    guru_storage_key: str | None
    learner_storage_key: str
    recitation_profile: str = "Kanchi"
    mantra_reference: str | None = None
    reference_phonetic_metadata: dict | None = None


class TranscriptionEngine(Protocol):
    engine_id: str
    version: str

    def transcribe(self, context: EngineContext) -> TranscriptResult: ...

    # Optional capability. A provider must return word-level boundaries and
    # confidence evidence; token alignment alone is not forced alignment.
    def forced_align(self, context: EngineContext, hypothesis_tokens: list[str]) -> dict: ...


class SvaraEngine(Protocol):
    engine_id: str
    version: str

    def evaluate(self, context: EngineContext) -> SvaraResult: ...


class AlignmentEngine(Protocol):
    engine_id: str
    version: str

    def forced_align(self, context: EngineContext, reference_tokens: list[str]) -> dict: ...


class PronunciationEngine(Protocol):
    """Independent acoustic assessment capability; ASR is not a scorer."""
    engine_id: str
    version: str

    def evaluate(self, context: EngineContext, hypothesis_tokens: list[str] | None) -> PronunciationResult: ...
