"""Provisional Sanskrit grapheme-to-phoneme reference generation.

This module derives an expected sound sequence from reviewed Devanagari text;
it does not infer sounds from audio and must never be used as a pronunciation
score. Sandhi, tradition-specific variants, and Vedic accents require review.
"""
from __future__ import annotations

import unicodedata

from app.services.engines.sanskrit_text import sanskrit_aksharas


PROFILE_ID = "classical_sanskrit_orthographic_g2p_v1"

_INDEPENDENT_VOWELS = {
    "अ": ("ɐ", "short"), "आ": ("aː", "long"),
    "इ": ("i", "short"), "ई": ("iː", "long"),
    "उ": ("u", "short"), "ऊ": ("uː", "long"),
    "ऋ": ("r̩", "short"), "ॠ": ("r̩ː", "long"),
    "ऌ": ("l̩", "short"), "ॡ": ("l̩ː", "long"),
    "ए": ("eː", "long"), "ऐ": ("ai̯", "diphthong"),
    "ओ": ("oː", "long"), "औ": ("au̯", "diphthong"),
}

_DEPENDENT_VOWELS = {
    "ा": ("aː", "long"), "ि": ("i", "short"), "ी": ("iː", "long"),
    "ु": ("u", "short"), "ू": ("uː", "long"), "ृ": ("r̩", "short"),
    "ॄ": ("r̩ː", "long"), "ॢ": ("l̩", "short"), "ॣ": ("l̩ː", "long"),
    "े": ("eː", "long"), "ै": ("ai̯", "diphthong"),
    "ो": ("oː", "long"), "ौ": ("au̯", "diphthong"),
}

# Internal feature labels intentionally retain Sanskrit distinctions without
# asserting dialect-specific acoustic realizations (for example ś vs palatal ṣ).
_CONSONANTS = {
    "क": ("k", "velar", "stop", "voiceless", "unaspirated"),
    "ख": ("kʰ", "velar", "stop", "voiceless", "aspirated"),
    "ग": ("g", "velar", "stop", "voiced", "unaspirated"),
    "घ": ("gʱ", "velar", "stop", "voiced", "breathy"),
    "ङ": ("ŋ", "velar", "nasal", "voiced", "none"),
    "च": ("c", "palatal", "affricate", "voiceless", "unaspirated"),
    "छ": ("cʰ", "palatal", "affricate", "voiceless", "aspirated"),
    "ज": ("ɟ", "palatal", "affricate", "voiced", "unaspirated"),
    "झ": ("ɟʱ", "palatal", "affricate", "voiced", "breathy"),
    "ञ": ("ɲ", "palatal", "nasal", "voiced", "none"),
    "ट": ("ʈ", "retroflex", "stop", "voiceless", "unaspirated"),
    "ठ": ("ʈʰ", "retroflex", "stop", "voiceless", "aspirated"),
    "ड": ("ɖ", "retroflex", "stop", "voiced", "unaspirated"),
    "ढ": ("ɖʱ", "retroflex", "stop", "voiced", "breathy"),
    "ण": ("ɳ", "retroflex", "nasal", "voiced", "none"),
    "त": ("t̪", "dental", "stop", "voiceless", "unaspirated"),
    "थ": ("t̪ʰ", "dental", "stop", "voiceless", "aspirated"),
    "द": ("d̪", "dental", "stop", "voiced", "unaspirated"),
    "ध": ("d̪ʱ", "dental", "stop", "voiced", "breathy"),
    "न": ("n̪", "dental", "nasal", "voiced", "none"),
    "प": ("p", "bilabial", "stop", "voiceless", "unaspirated"),
    "फ": ("pʰ", "bilabial", "stop", "voiceless", "aspirated"),
    "ब": ("b", "bilabial", "stop", "voiced", "unaspirated"),
    "भ": ("bʱ", "bilabial", "stop", "voiced", "breathy"),
    "म": ("m", "bilabial", "nasal", "voiced", "none"),
    "य": ("j", "palatal", "approximant", "voiced", "none"),
    "र": ("r", "alveolar", "trill", "voiced", "none"),
    "ल": ("l", "alveolar", "lateral", "voiced", "none"),
    "व": ("ʋ", "labiodental", "approximant", "voiced", "none"),
    "ळ": ("ɭ", "retroflex", "lateral", "voiced", "none"),
    "श": ("ɕ", "palatal", "sibilant", "voiceless", "none"),
    "ष": ("ʂ", "retroflex", "sibilant", "voiceless", "none"),
    "स": ("s", "dental", "sibilant", "voiceless", "none"),
    "ह": ("ɦ", "glottal", "fricative", "voiced", "none"),
}

_ACCENTS = {"॑": "udatta", "॒": "anudatta"}
_NASAL_SIGNS = {"ं": "anusvara", "ँ": "chandrabindu"}


class G2PError(ValueError):
    pass


def _phone(symbol: str, grapheme: str, kind: str, **features: str) -> dict:
    return {"symbol": symbol, "source_grapheme": grapheme, "kind": kind, "features": features}


def transcribe_word_to_phonemes(word: str) -> dict:
    """Return provisional IPA-like segments grouped by written akṣara.

    Avagraha is returned as unresolved rather than silently applying a
    tradition-specific sandhi rule. Unknown Devanagari letters fail explicitly.
    """
    normalized = unicodedata.normalize("NFC", word or "")
    if not normalized or any(char.isspace() for char in normalized):
        raise G2PError("Expected one non-empty Sanskrit word")

    clusters = sanskrit_aksharas(normalized)
    akshara_rows: list[dict] = []
    unsupported: list[str] = []
    pending_accent: str | None = None

    for cluster_index, cluster in enumerate(clusters):
        phones: list[dict] = []
        cursor = 0
        while cursor < len(cluster):
            char = cluster[cursor]
            if char in _ACCENTS:
                for previous_phone in reversed(phones):
                    if previous_phone["kind"] == "vowel":
                        previous_phone["features"]["vedic_accent"] = _ACCENTS[char]
                        break
                else:
                    pending_accent = _ACCENTS[char]
                cursor += 1
                continue
            if char in _INDEPENDENT_VOWELS:
                symbol, length = _INDEPENDENT_VOWELS[char]
                item = _phone(symbol, char, "vowel", length=length)
                if pending_accent:
                    item["features"]["vedic_accent"] = pending_accent
                    pending_accent = None
                phones.append(item)
                cursor += 1
                continue
            if char in _CONSONANTS:
                symbol, place, manner, voicing, aspiration = _CONSONANTS[char]
                phones.append(_phone(symbol, char, "consonant", place=place, manner=manner,
                                     voicing=voicing, aspiration=aspiration))
                cursor += 1
                if cursor < len(cluster) and cluster[cursor] == "्":
                    cursor += 1
                    continue
                if cursor < len(cluster) and cluster[cursor] in _DEPENDENT_VOWELS:
                    vowel_symbol, length = _DEPENDENT_VOWELS[cluster[cursor]]
                    item = _phone(vowel_symbol, char + cluster[cursor], "vowel", length=length)
                    if pending_accent:
                        item["features"]["vedic_accent"] = pending_accent
                        pending_accent = None
                    phones.append(item)
                    cursor += 1
                else:
                    item = _phone("ɐ", char, "vowel", length="short", source="inherent_a")
                    if pending_accent:
                        item["features"]["vedic_accent"] = pending_accent
                        pending_accent = None
                    phones.append(item)
                continue
            if char in _NASAL_SIGNS:
                nasal_kind = _NASAL_SIGNS[char]
                phones.append(_phone("◌̃" if nasal_kind == "chandrabindu" else "ṃ", char,
                                     "nasalization" if nasal_kind == "chandrabindu" else "anusvara",
                                     place="context_dependent"))
                cursor += 1
                continue
            if char == "ः":
                phones.append(_phone("ḥ", char, "visarga", realization="context_dependent"))
                cursor += 1
                continue
            if char == "ऽ":
                unsupported.append("avagraha_requires_sandhi_resolution")
                cursor += 1
                continue
            if char == "ॐ":
                phones.extend([
                    _phone("oː", char, "vowel", length="long"),
                    _phone("ṃ", char, "anusvara", place="context_dependent"),
                ])
                cursor += 1
                continue
            if char == "्":
                # A virāma is normally consumed with its consonant above.
                unsupported.append("orphan_virama")
                cursor += 1
                continue
            if char in "।॥,;:!?·-–—()[]{}\"'":
                cursor += 1
                continue
            if unicodedata.category(char).startswith("M"):
                unsupported.append(f"unmapped_combining_mark_U+{ord(char):04X}")
                cursor += 1
                continue
            raise G2PError(f"Unsupported Sanskrit grapheme U+{ord(char):04X}: {char}")

        akshara_rows.append({"akshara_order": cluster_index + 1,
                             "akshara": cluster, "phonemes": phones})

    return {
        "profile_id": PROFILE_ID,
        "status": "candidate" if not unsupported else "partial",
        "text": normalized,
        "model_evaluation_eligible": False,
        "interpretation": "Orthographic expected-phoneme hypothesis only; not audio evidence or a pronunciation score.",
        "aksharas": akshara_rows,
        "unsupported_features": sorted(set(unsupported)),
    }


def transcribe_text_to_phonemes(text: str) -> dict:
    normalized = unicodedata.normalize("NFC", text or "")
    normalized = normalized.replace("।", " ").replace("॥", " ")
    normalized = " ".join(normalized.split())
    words = normalized.split()
    word_rows = [
        {"word_order": order, "word": word, **transcribe_word_to_phonemes(word)}
        for order, word in enumerate(words, 1)
    ]
    return {
        "profile_id": PROFILE_ID,
        "status": "partial" if any(row["status"] == "partial" for row in word_rows) else "candidate",
        "text": text,
        "model_evaluation_eligible": False,
        "words": word_rows,
        "interpretation": "Expected phoneme candidates from text; requires Guru review and a separate validated acoustic assessor.",
    }
