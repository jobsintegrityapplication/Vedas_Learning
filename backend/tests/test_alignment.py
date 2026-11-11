from app.services.alignment import align_tokens, score_alignment
from app.services.content_integrity import tokenize_guru_text
from app.services.evaluation import UNAVAILABLE_SVARA, evaluate_hypothesis


def test_align_detects_skipped_word():
    result = align_tokens(["a", "b", "c"], ["a", "c"])
    assert result.skipped == ["b"]
    assert result.substituted == []
    assert result.extra == []
    assert result.matched == 2


def test_align_detects_substitution():
    result = align_tokens(["a", "b"], ["a", "x"])
    assert result.substituted == [{"expected": "b", "actual": "x"}]
    assert result.skipped == []
    assert result.extra == []


def test_align_detects_extra():
    result = align_tokens(["a"], ["a", "c"])
    assert result.extra == ["c"]
    assert result.skipped == []
    assert result.matched == 1


def test_word_match_score_uses_90_percent_threshold():
    reference = [f"word-{index}" for index in range(20)]
    one_substitution = reference[:-1] + ["wrong"]
    score = score_alignment(align_tokens(reference, one_substitution), 90.0)
    assert score["matched"] == 19
    assert score["match_percent"] == 95.0
    assert score["meets_threshold"] is True

    two_substitutions = reference[:-2] + ["wrong-a", "wrong-b"]
    score = score_alignment(align_tokens(reference, two_substitutions), 90.0)
    assert score["match_percent"] == 90.0
    assert score["meets_threshold"] is True
    three_substitutions = reference[:-3] + ["wrong-a", "wrong-b", "wrong-c"]
    score = score_alignment(align_tokens(reference, three_substitutions), 90.0)
    assert score["match_percent"] == 85.0
    assert score["meets_threshold"] is False


def test_empty_word_sequence_never_passes():
    score = score_alignment(align_tokens([], []), 90.0)
    assert score["match_percent"] == 0.0
    assert score["meets_threshold"] is False


def test_tokenize_preserves_sanskrit_characters():
    text = "संगच्छध्वं संवदध्वं"
    tokens = tokenize_guru_text(text)
    assert tokens == ["संगच्छध्वं", "संवदध्वं"]


def test_evaluation_without_engine_is_honest():
    report = evaluate_hypothesis(["a", "b"], hypothesis_tokens=None)
    assert report["engine_status"] == "not_configured"
    assert report["word_accuracy"]["status"] == "unavailable"
    assert report["pronunciation"]["status"] == "unavailable"
    assert report["svara"]["status"] == "unavailable"
    assert "svara" in report["svara"]["reason"].lower() or "Vedic" in report["svara"]["reason"]
    assert UNAVAILABLE_SVARA in report["svara"]["reason"]
