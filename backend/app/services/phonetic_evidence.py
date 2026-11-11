"""Fail-closed validation of acoustic engine feature findings.

This module does not infer Sanskrit phonetics. It only forwards findings from a
configured acoustic provider when the provider supplies feature, confidence,
time span, observed/reference values, and actionable guidance.
"""

SUPPORTED_FEATURES = {
    "vowel_length", "vowel_duration", "consonant_place", "consonant_manner", "consonant_voicing",
    "aspiration", "visarga", "anusvara", "vedic_accent",
}


def validated_feature_findings(items: list[dict] | None) -> tuple[list[dict], list[str]]:
    accepted: list[dict] = []
    unsupported: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature")
        confidence = item.get("confidence")
        time_span = item.get("time_span_ms")
        if feature not in SUPPORTED_FEATURES:
            if feature:
                unsupported.add(str(feature))
            continue
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            continue
        if not isinstance(time_span, dict) or not isinstance(time_span.get("start"), int) or not isinstance(time_span.get("end"), int) or time_span["end"] <= time_span["start"]:
            continue
        if "reference_value" not in item or "observed_value" not in item:
            continue
        guidance = item.get("correction_guidance")
        if not isinstance(guidance, str) or not guidance.strip():
            continue
        accepted.append({
            "word_order": item.get("word_order"),
            "expected_word": item.get("expected_word"),
            "feature": feature,
            "reference_value": item["reference_value"],
            "observed_value": item["observed_value"],
            "time_span_ms": time_span,
            "confidence": float(confidence),
            "correction_guidance": guidance.strip(),
            "evidence_source": item.get("evidence_source"),
        })
    return accepted, sorted(unsupported)
