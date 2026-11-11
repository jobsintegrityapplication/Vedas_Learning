import numpy as np
import pytest

from app.services.engines.ctc_alignment import AlignmentError, forced_align
from app.services.engines.sanskrit_text import normalize_sanskrit_text, sanskrit_aksharas


def _log_probs(best_ids, class_count=3):
    probabilities = np.full((len(best_ids), class_count), 0.01, dtype=np.float64)
    for frame, token_id in enumerate(best_ids):
        probabilities[frame, token_id] = 0.98
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return np.log(probabilities)


def test_ctc_alignment_places_known_target_through_blank_frames():
    path = forced_align(_log_probs([1, 0, 2, 2, 0]), [1, 2], blank_id=0)
    assert [state for state in path if state % 2 == 1] == [1, 3, 3]


def test_ctc_alignment_distinguishes_repeated_target_labels():
    path = forced_align(_log_probs([1, 0, 1]), [1, 1], blank_id=0)
    assert path == [1, 2, 3]


def test_ctc_alignment_rejects_too_short_audio_for_repeated_target():
    with pytest.raises(AlignmentError):
        forced_align(_log_probs([1, 1]), [1, 1], blank_id=0)


def test_sanskrit_normalizer_drops_accents_and_punctuation_only():
    assert normalize_sanskrit_text("ऋ॒तेनादित्यास्तिष्ठन्ति ।") == "ऋतेनादित्यास्तिष्ठन्ति"


def test_akshara_groups_dependent_signs_and_conjuncts():
    assert sanskrit_aksharas("सत्येन") == ["स", "त्ये", "न"]
