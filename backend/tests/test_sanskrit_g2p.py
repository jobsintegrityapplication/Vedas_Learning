import pytest

from app.services.sanskrit_g2p import (
    G2PError,
    transcribe_text_to_phonemes,
    transcribe_word_to_phonemes,
)


def _symbols(word):
    result = transcribe_word_to_phonemes(word)
    return [phone["symbol"] for akshara in result["aksharas"] for phone in akshara["phonemes"]]


def _phones(word):
    result = transcribe_word_to_phonemes(word)
    return [phone for akshara in result["aksharas"] for phone in akshara["phonemes"]]


def test_g2p_distinguishes_short_and_long_vowels():
    assert _symbols("क") == ["k", "ɐ"]
    assert _symbols("का") == ["k", "aː"]
    assert _phones("का")[-1]["features"]["length"] == "long"


def test_g2p_retains_dental_retroflex_and_aspiration_contrasts():
    assert _phones("त")[0]["features"]["place"] == "dental"
    assert _phones("ट")[0]["features"]["place"] == "retroflex"
    assert _phones("थ")[0]["features"]["aspiration"] == "aspirated"
    assert _phones("त")[0]["features"]["aspiration"] == "unaspirated"


def test_g2p_keeps_the_three_sibilants_distinct():
    assert _symbols("श") == ["ɕ", "ɐ"]
    assert _symbols("ष") == ["ʂ", "ɐ"]
    assert _symbols("स") == ["s", "ɐ"]


def test_g2p_expands_conjuncts_without_inserting_vowels_between_them():
    assert _symbols("क्ष") == ["k", "ʂ", "ɐ"]
    assert _symbols("सत्य") == ["s", "ɐ", "t̪", "j", "ɐ"]


def test_g2p_preserves_context_dependent_nasal_and_visarga_labels():
    kinds = [phone["kind"] for phone in _phones("संः")]
    assert kinds == ["consonant", "vowel", "anusvara", "visarga"]
    assert _phones("संः")[2]["features"]["place"] == "context_dependent"


def test_g2p_attaches_vedic_accent_to_vowel_and_preserves_it_in_text_mode():
    output = transcribe_text_to_phonemes("इ॒न्द्रः ।")
    assert output["words"][0]["text"] == "इ॒न्द्रः"
    phones = [phone for akshara in output["words"][0]["aksharas"] for phone in akshara["phonemes"]]
    vowel = next(phone for phone in phones if phone["kind"] == "vowel")
    assert vowel["features"]["vedic_accent"] == "anudatta"


def test_g2p_marks_avagraha_as_unresolved_instead_of_guessing_sandhi():
    output = transcribe_word_to_phonemes("सोऽहम्")
    assert output["status"] == "partial"
    assert "avagraha_requires_sandhi_resolution" in output["unsupported_features"]
    assert transcribe_text_to_phonemes("सोऽहम्")["status"] == "partial"


def test_g2p_rejects_unmapped_non_devanagari_text():
    with pytest.raises(G2PError):
        transcribe_word_to_phonemes("satya")
