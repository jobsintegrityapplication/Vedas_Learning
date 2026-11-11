"""Compare normalized word timing from independent known-text alignments.

These are descriptive timing diagnostics. They are not pronunciation scores,
and naturally different speaking speeds are removed by duration normalization.
"""


def compare_normalized_word_timing(student_alignment: dict, guru_alignment: dict,
                                   student_duration_ms: int | None,
                                   guru_duration_ms: int | None) -> dict:
    if not isinstance(student_duration_ms, int) or not isinstance(guru_duration_ms, int) or min(student_duration_ms, guru_duration_ms) <= 0:
        return {"status": "unavailable", "reason": "Audio durations are unavailable for normalized timing comparison.", "score": None, "words": []}
    student_words = student_alignment.get("words") if isinstance(student_alignment, dict) else None
    guru_words = guru_alignment.get("words") if isinstance(guru_alignment, dict) else None
    if not isinstance(student_words, list) or not isinstance(guru_words, list) or len(student_words) != len(guru_words) or not student_words:
        return {"status": "unavailable", "reason": "Both recordings need complete known-text word alignments.", "score": None, "words": []}

    result = []
    previous_student_end = previous_guru_end = 0
    for order, (student, guru) in enumerate(zip(student_words, guru_words), 1):
        if (not isinstance(student, dict) or not isinstance(guru, dict)
                or student.get("word_order") != order or guru.get("word_order") != order
                or student.get("word") != guru.get("word")
                or not all(isinstance(row.get(field), int) for row in (student, guru) for field in ("start_ms", "end_ms"))
                or student["end_ms"] <= student["start_ms"] or guru["end_ms"] <= guru["start_ms"]
                or student["end_ms"] > student_duration_ms or guru["end_ms"] > guru_duration_ms):
            return {"status": "unavailable", "reason": "Word order or boundaries differ between the two candidate alignments.", "score": None, "words": []}
        student_start = student["start_ms"] / student_duration_ms
        student_end = student["end_ms"] / student_duration_ms
        guru_start = guru["start_ms"] / guru_duration_ms
        guru_end = guru["end_ms"] / guru_duration_ms
        student_pause = (student["start_ms"] - previous_student_end) / student_duration_ms
        guru_pause = (guru["start_ms"] - previous_guru_end) / guru_duration_ms
        result.append({
            "word_order": order,
            "word": student["word"],
            "student_normalized_start": round(student_start, 5),
            "guru_normalized_start": round(guru_start, 5),
            "normalized_start_delta": round(student_start - guru_start, 5),
            "student_normalized_duration": round(student_end - student_start, 5),
            "guru_normalized_duration": round(guru_end - guru_start, 5),
            "normalized_duration_delta": round((student_end - student_start) - (guru_end - guru_start), 5),
            "student_pause_before": round(max(0.0, student_pause), 5),
            "guru_pause_before": round(max(0.0, guru_pause), 5),
            "pause_before_delta": round(max(0.0, student_pause) - max(0.0, guru_pause), 5),
        })
        previous_student_end = student["end_ms"]
        previous_guru_end = guru["end_ms"]
    return {
        "status": "candidate_only",
        "score": None,
        "words": result,
        "interpretation": (
            "Descriptive relative word and pause timing from two independent forced alignments. "
            "Durations are normalized for total clip length; differences are not pronunciation errors or a pass/fail score."
        ),
    }
