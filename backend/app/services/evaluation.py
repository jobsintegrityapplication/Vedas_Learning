from app.core.config import get_settings
from app.services.alignment import AlignmentResult, align_tokens
from app.services.engines.base import UNAVAILABLE_ASR, UNAVAILABLE_PRONUNCIATION, UNAVAILABLE_SVARA
from app.services.engines.registry import engine_is_configured


def capability_report(alignment: AlignmentResult | None = None) -> dict:
    settings = get_settings()
    configured = engine_is_configured()
    word_status = "unavailable"
    alignment_payload = None
    word_score = None
    word_reason = UNAVAILABLE_ASR
    if configured and alignment is not None:
        word_status = "completed"
        alignment_payload = alignment.as_dict()
        denominator = max(len(alignment.reference_tokens), len(alignment.hypothesis_tokens), 1)
        word_score = round(alignment.matched * 100.0 / denominator, 2)
        word_reason = "Compared hypothesized tokens against Guru reference tokens."
    word_threshold_met = word_score is not None and word_score >= settings.word_match_pass_threshold_percent
    return {
        "engine_id": settings.evaluation_engine if configured else "none",
        "engine_version": settings.evaluation_engine_version,
        "engine_status": "configured" if configured else "not_configured",
        "word_accuracy": {
            "status": word_status,
            "reason": word_reason,
            "alignment": alignment_payload,
            "match_percent": word_score,
            "pass_threshold_percent": settings.word_match_pass_threshold_percent,
            "meets_word_threshold": word_threshold_met,
        },
        "pronunciation": {
            "status": "unavailable",
            "reason": UNAVAILABLE_PRONUNCIATION,
            "scores": None,
        },
        "svara": {
            "status": "unavailable",
            "reason": UNAVAILABLE_SVARA,
        },
        "accepted": False,
        "acceptance_reason": "Validated pronunciation scoring is unavailable; this attempt cannot be accepted.",
    }


def evaluate_hypothesis(reference_tokens: list[str], hypothesis_tokens: list[str] | None) -> dict:
    alignment = None
    if hypothesis_tokens is not None:
        alignment = align_tokens(reference_tokens, hypothesis_tokens)
    return capability_report(alignment)
