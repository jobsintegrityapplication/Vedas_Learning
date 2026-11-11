from __future__ import annotations

import unicodedata


def normalize_sanskrit_text(text: str) -> str:
    """Normalize supported Sanskrit orthography for the Devanagari ASR models."""
    text = unicodedata.normalize("NFC", text or "")
    output: list[str] = []
    for char in text:
        codepoint = ord(char)
        if codepoint in {0x0951, 0x0952} or 0x1CD0 <= codepoint <= 0x1CFF:
            # Vedic accent marks attach to a syllable; dropping them must not
            # split the surrounding word into separate alignment tokens.
            continue
        elif unicodedata.category(char)[0] in {"L", "M"}:
            output.append(char)
        else:
            output.append(" ")
    return " ".join("".join(output).split())


def sanskrit_aksharas(word: str) -> list[str]:
    """Group Unicode combining signs and virama conjuncts into orthographic akṣaras."""
    result: list[str] = []
    for char in unicodedata.normalize("NFC", word):
        if not result:
            result.append(char)
        elif unicodedata.category(char).startswith("M") or char in {"\u200c", "\u200d"}:
            result[-1] += char
        elif result[-1].endswith(("\u094d", "\u200d")):
            result[-1] += char
        else:
            result.append(char)
    return result
