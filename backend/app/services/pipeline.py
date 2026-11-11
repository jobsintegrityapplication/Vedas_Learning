from __future__ import annotations

from app.core.config import get_settings
from app.services.alignment import align_tokens, score_alignment
from app.services.audio_preprocess import preprocess_audio
from app.services.content_integrity import tokenize_guru_text
from app.services.engines.base import EngineContext
from app.services.engines.registry import (
    alignment_engine_is_configured,
    engine_is_configured,
    get_alignment_engine,
    get_pronunciation_engine,
    get_svara_engine,
    get_transcription_engine,
)
from app.services.guru_student_timing import compare_normalized_word_timing
from app.services.phonetic_evidence import validated_feature_findings


def profile_reference_unavailable(profile: str, mantra_reference: str | None, reason: str) -> dict:
    """Fail closed when there is no reviewed source text for the selected lineage."""
    threshold = get_settings().word_match_pass_threshold_percent
    return {
        "engine_id": "none", "engine_version": "0", "engine_status": "not_configured", "status": "unavailable",
        "recitation_profile": profile, "mantra_reference": mantra_reference,
        "validation": None, "preprocessing": None,
        "transcription": {"status": "unavailable", "reason": reason, "source": None, "tokens": None},
        "word_accuracy": {"status": "unavailable", "reason": reason, "alignment": None, "evidence": None,
                          "match_percent": None, "pass_threshold_percent": threshold, "meets_word_threshold": False,
                          "correction_guidance": []},
        "forced_alignment": {"status": "unavailable", "reason": reason, "words": []},
        "guru_student_timing_comparison": {"status": "unavailable", "score": None, "words": [], "reason": reason},
        "pronunciation": {"status": "unavailable", "engine_id": "none", "engine_version": "0",
                          "reason": "No approved profile-specific phonetic reference is available.",
                          "mismatches": [], "scores": None, "overall_percent": None, "pass_threshold_percent": threshold,
                          "meets_threshold": False, "confidence": None, "phonetic_evidence": [], "correction_guidance": []},
        "svara": {"status": "unavailable", "reason": "No reviewed tradition-specific accent reference or validated svara engine is available.", "engine_id": "none", "evidence": None},
        "reference_text_status": "unavailable", "reference_audio_status": "unavailable",
        "diagnostic_only": False,
        "accepted": False,
        "acceptance_reason": "A reviewed, rights-cleared text for the selected recitation profile is unavailable; this attempt cannot be accepted.",
    }


def _validated_alignment(candidate: object) -> dict:
    if not isinstance(candidate, dict) or candidate.get("status") != "completed" or not isinstance(candidate.get("words"), list):
        return {"status": "unavailable", "reason": "Provider did not return a completed word alignment.", "words": []}
    words = candidate["words"]
    if not words:
        return {"status": "unavailable", "reason": "Provider returned no word boundaries.", "words": []}
    for item in words:
        if not isinstance(item, dict):
            return {"status": "unavailable", "reason": "Provider returned malformed word evidence.", "words": []}
        start, end, confidence = item.get("start_ms"), item.get("end_ms"), item.get("confidence")
        if (not isinstance(item.get("word_order"), int) or not item.get("word")
                or not isinstance(start, int) or not isinstance(end, int) or end <= start
                or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
            return {"status": "unavailable", "reason": "Word evidence requires ordered token, valid timestamps, and confidence 0–1.", "words": []}
    return candidate


def run_evaluation_pipeline(
    *,
    learner_bytes: bytes,
    learner_filename: str,
    learner_content_type: str,
    learner_storage_key: str,
    guru_text: str,
    guru_bytes: bytes | None,
    guru_filename: str | None,
    guru_content_type: str | None,
    guru_storage_key: str | None,
    lesson_slug: str,
    recitation_profile: str = "Kanchi",
    mantra_reference: str | None = None,
    reference_tokens: list[str] | None = None,
    reference_phonetic_metadata: dict | None = None,
    reference_is_reviewed: bool = True,
) -> dict:
    learner = preprocess_audio(learner_bytes, learner_filename, learner_content_type)
    guru = None
    if guru_bytes and guru_filename:
        guru = preprocess_audio(guru_bytes, guru_filename, guru_content_type or "audio/wav")

    reference_tokens = reference_tokens if reference_tokens is not None else tokenize_guru_text(guru_text)
    transcriber = get_transcription_engine()
    aligner = get_alignment_engine()
    pronunciation_engine = get_pronunciation_engine()
    svara_engine = get_svara_engine()
    context = EngineContext(
        lesson_slug=lesson_slug,
        reference_tokens=reference_tokens,
        learner_filename=learner_filename,
        learner_audio=learner,
        guru_audio=guru,
        guru_storage_key=guru_storage_key,
        learner_storage_key=learner_storage_key,
        recitation_profile=recitation_profile,
        mantra_reference=mantra_reference,
        reference_phonetic_metadata=reference_phonetic_metadata,
    )
    transcript = transcriber.transcribe(context)
    hypothesis = transcript.tokens if transcript.status == "completed" else None
    pronunciation = pronunciation_engine.evaluate(context, hypothesis)
    phonetic_findings, unsupported_phonetic_features = validated_feature_findings(pronunciation.evidence or pronunciation.mismatches)
    svara = svara_engine.evaluate(context)
    svara_payload = svara.evidence if isinstance(svara.evidence, dict) else {}
    accent_findings, unsupported_accent_features = validated_feature_findings(svara_payload.get("findings"))

    alignment_payload = None
    alignment_result = None
    word_status = "unavailable"
    word_reason = transcript.reason
    evidence = None
    if hypothesis is not None:
        alignment_result = align_tokens(reference_tokens, hypothesis)
        alignment_payload = alignment_result.as_dict()
        threshold = get_settings().word_match_pass_threshold_percent
        score = score_alignment(alignment_result, threshold)
        evidence = {
            **score,
            "omissions": alignment_result.skipped,
            "substitutions": alignment_result.substituted,
            "insertions": alignment_result.extra,
            "meets_word_threshold": score["meets_threshold"],
            "source": transcript.source,
            "transcript_confidence_declared": transcript.confidence_declared,
            "transcript_confidence": transcript.confidence,
            "token_confidences": transcript.token_confidences,
        }
        word_corrections = [
            {"issue": "omission", "target_word": token,
             "guidance": f"Listen to the {recitation_profile} reference for this word, then repeat it in mantra order."}
            for token in alignment_result.skipped
        ] + [
            {"issue": "substitution", "target_word": item["expected"], "recognized_word": item["actual"],
             "guidance": f"Compare the recognized word with the {recitation_profile} target word and repeat from its word clip when available."}
            for item in alignment_result.substituted
        ]
        word_status = "completed"
        word_reason = (
            f"Compared recognized tokens with the {recitation_profile} reference text. "
            + transcript.reason
        )

    forced_alignment = {
        "status": "unavailable",
        "reason": "No validated known-text alignment provider is configured.",
        "words": [],
    }
    guru_forced_alignment = {
        "status": "unavailable",
        "reason": "No validated known-text alignment provider is configured.",
        "words": [],
    }
    align_method = getattr(aligner, "forced_align", None)
    if reference_tokens and alignment_engine_is_configured() and callable(align_method):
        try:
            candidate = align_method(context, reference_tokens)
            forced_alignment = _validated_alignment(candidate)
        except Exception as exc:
            forced_alignment = {"status": "unavailable", "reason": f"Known-text alignment provider failed: {type(exc).__name__}", "words": []}
        if guru is not None:
            try:
                guru_context = EngineContext(
                    lesson_slug=lesson_slug,
                    reference_tokens=reference_tokens,
                    learner_filename=guru_filename or "guru-reference",
                    learner_audio=guru,
                    guru_audio=None,
                    guru_storage_key=guru_storage_key,
                    learner_storage_key=guru_storage_key or "guru/reference",
                    recitation_profile=recitation_profile,
                    mantra_reference=mantra_reference,
                    reference_phonetic_metadata=reference_phonetic_metadata,
                )
                guru_candidate = align_method(guru_context, reference_tokens)
                guru_forced_alignment = _validated_alignment(guru_candidate)
            except Exception as exc:
                guru_forced_alignment = {"status": "unavailable", "reason": f"Guru reference alignment failed: {type(exc).__name__}", "words": []}
    else:
        # Compatibility for existing custom providers that implement the old
        # optional method directly on the transcription engine.
        legacy_align = getattr(transcriber, "forced_align", None)
        if hypothesis is not None and callable(legacy_align):
            try:
                forced_alignment = _validated_alignment(legacy_align(context, hypothesis))
            except Exception as exc:
                forced_alignment = {"status": "unavailable", "reason": f"Legacy forced alignment failed: {type(exc).__name__}", "words": []}

    timing_comparison = compare_normalized_word_timing(
        forced_alignment,
        guru_forced_alignment,
        learner.inspection.duration_ms,
        guru.inspection.duration_ms if guru else None,
    )

    settings = get_settings()
    pronunciation_score = None
    if isinstance(pronunciation.scores, dict):
        candidate_score = pronunciation.scores.get("overall_percent")
        if isinstance(candidate_score, (int, float)) and 0 <= candidate_score <= 100:
            pronunciation_score = round(float(candidate_score), 2)
    pronunciation_status = (
        "completed"
        if pronunciation.status == "completed" and pronunciation_score is not None
        else "unavailable"
    )
    word_match_percent = evidence.get("match_percent") if evidence else None
    word_threshold_met = bool(evidence and evidence.get("meets_word_threshold"))
    pronunciation_threshold_met = bool(
        pronunciation_status == "completed"
        and pronunciation_score is not None
        and pronunciation_score >= settings.word_match_pass_threshold_percent
    )
    reference_audio_available = guru is not None
    accepted = reference_is_reviewed and word_threshold_met and reference_audio_available
    if not reference_is_reviewed:
        acceptance_reason = "Diagnostic only: compared with unreviewed lesson text. This attempt cannot be accepted or unlock progress."
    elif word_match_percent is None:
        acceptance_reason = "A validated Sanskrit transcription engine is not configured, so word matching cannot be scored."
    elif not word_threshold_met:
        acceptance_reason = f"Word match is below the required {settings.word_match_pass_threshold_percent:g}%. Please listen and retry."
    elif not reference_audio_available:
        acceptance_reason = "Word match met the threshold, but approved Guru reference audio is unavailable for this lesson; this attempt is not accepted."
    else:
        acceptance_reason = f"Word match met the required {settings.word_match_pass_threshold_percent:g}% threshold against the reviewed reference words."
    configured = engine_is_configured()
    overall = "completed" if word_status == "completed" or pronunciation_status == "completed" or forced_alignment.get("status") == "completed" else (
        "not_configured" if not configured else "unavailable"
    )
    return {
        "engine_id": transcriber.engine_id if configured else "none",
        "engine_version": settings.evaluation_engine_version if not configured else transcriber.version,
        "engine_status": "configured" if configured else "not_configured",
        "recitation_profile": recitation_profile,
        "mantra_reference": mantra_reference,
        "reference_text_status": "profile_specific_reviewed" if reference_is_reviewed else "development_candidate_unreviewed",
        "diagnostic_only": not reference_is_reviewed,
        "reference_audio_status": "available" if guru is not None else "unavailable",
        "status": overall,
        "storage": {
            "learner_key": learner_storage_key,
            "guru_key": guru_storage_key,
            "namespaces": {"learner": "learner/", "guru": "guru/"},
        },
        "validation": learner.inspection.as_dict(),
        "preprocessing": learner.as_dict(),
        "guru_audio": {
            "present": guru is not None,
            "preprocessing": guru.as_dict() if guru else None,
        },
        "transcription": {
            "status": transcript.status,
            "reason": transcript.reason,
            "source": transcript.source,
            "tokens": hypothesis,
            "evaluation_passed": transcript.evaluation_passed,
        },
        "word_accuracy": {
            "status": word_status,
            "reason": word_reason,
            "alignment": alignment_payload,
            "evidence": evidence,
            "match_percent": word_match_percent,
            "pass_threshold_percent": settings.word_match_pass_threshold_percent,
            "meets_word_threshold": word_threshold_met,
            "correction_guidance": word_corrections if hypothesis is not None else [],
        },
        "forced_alignment": forced_alignment,
        "guru_student_timing_comparison": timing_comparison,
        "alignment_engine_id": forced_alignment.get("engine_id", "none"),
        "alignment_engine_version": forced_alignment.get("engine_version", "0"),
        "pronunciation": {
            "status": pronunciation_status,
            "engine_id": pronunciation_engine.engine_id,
            "engine_version": pronunciation_engine.version,
            "reason": pronunciation.reason,
            "mismatches": phonetic_findings,
            "scores": pronunciation.scores,
            "overall_percent": pronunciation_score,
            "pass_threshold_percent": settings.word_match_pass_threshold_percent,
            "meets_threshold": pronunciation_threshold_met,
            "confidence": pronunciation.confidence,
            "phonetic_evidence": phonetic_findings,
            "unsupported_features": unsupported_phonetic_features,
            "correction_guidance": [item["correction_guidance"] for item in phonetic_findings],
        },
        "svara": {
            "status": svara.status if accent_findings else "unavailable",
            "reason": svara.reason,
            "engine_id": svara.engine_id,
            "evidence": accent_findings,
            "unsupported_features": unsupported_accent_features,
            "confidence": svara.confidence,
            "correction_guidance": [item["correction_guidance"] for item in accent_findings] or svara.correction_guidance,
        },
        "accepted": accepted,
        "acceptance_reason": acceptance_reason,
    }


def public_report(report: dict | None) -> dict | None:
    if not report:
        return None
    copy = {
        key: value
        for key, value in report.items()
        if key not in {"storage"}
    }
    copy["storage"] = {
        "namespaces": (report.get("storage") or {}).get("namespaces"),
        "guru_audio_present": bool((report.get("storage") or {}).get("guru_key")),
    }
    return copy


def apply_report(evaluation, report: dict) -> None:
    evaluation.status = report["status"]
    evaluation.engine_id = report["engine_id"]
    evaluation.engine_version = report["engine_version"]
    evaluation.word_accuracy_status = report["word_accuracy"]["status"]
    evaluation.pronunciation_status = report["pronunciation"]["status"]
    evaluation.svara_status = report["svara"]["status"]
    evaluation.alignment = report["word_accuracy"]["alignment"]
    evaluation.report = report
    evaluation.hypothesis_tokens = report["transcription"]["tokens"]
    evaluation.message = (
        report["word_accuracy"]["reason"]
        + " "
        + report["pronunciation"]["reason"]
        + " "
        + report["svara"]["reason"]
    )
