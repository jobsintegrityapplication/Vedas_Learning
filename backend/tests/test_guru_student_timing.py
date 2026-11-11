from app.services.guru_student_timing import compare_normalized_word_timing


def test_relative_timing_normalizes_speaking_speed_without_producing_a_score():
    guru = {"words": [
        {"word_order": 1, "word": "गुरु", "start_ms": 100, "end_ms": 400},
        {"word_order": 2, "word": "नमः", "start_ms": 600, "end_ms": 1000},
    ]}
    student = {"words": [
        {"word_order": 1, "word": "गुरु", "start_ms": 200, "end_ms": 800},
        {"word_order": 2, "word": "नमः", "start_ms": 1200, "end_ms": 2000},
    ]}
    result = compare_normalized_word_timing(student, guru, 2000, 1000)
    assert result["status"] == "candidate_only"
    assert result["score"] is None
    assert result["words"][0]["normalized_duration_delta"] == 0
    assert result["words"][1]["pause_before_delta"] == 0


def test_relative_timing_withholds_output_for_misaligned_words():
    student = {"words": [{"word_order": 1, "word": "गुरु", "start_ms": 0, "end_ms": 100}]}
    guru = {"words": [{"word_order": 1, "word": "नमः", "start_ms": 0, "end_ms": 100}]}
    result = compare_normalized_word_timing(student, guru, 1000, 1000)
    assert result["status"] == "unavailable"
    assert result["words"] == []
    assert result["score"] is None


def test_relative_timing_withholds_out_of_bounds_alignment():
    alignment = {"words": [{"word_order": 1, "word": "गुरु", "start_ms": 0, "end_ms": 1100}]}
    result = compare_normalized_word_timing(alignment, alignment, 1000, 1000)
    assert result["status"] == "unavailable"
    assert result["words"] == []
