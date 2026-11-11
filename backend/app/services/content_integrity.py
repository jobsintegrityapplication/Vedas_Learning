import hashlib
import json
import re


GURU_FIELDS = (
    "sanskrit_text",
    "meaning",
    "canonical_reference",
    "transliteration",
    "translation",
    "translations",
    "word_meanings",
)

_REFERENCE_SHLOKA = re.compile(r"(\d+(?:\.\d+)*)\s*$")


def fingerprint(sanskrit_text: str, meaning: str) -> str:
    payload = f"{sanskrit_text}\n{meaning}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def tokenize_guru_text(sanskrit_text: str) -> list[str]:
    """Whitespace tokenization only. Characters are never rewritten."""
    return [part for part in sanskrit_text.replace("\n", " ").split(" ") if part]


def shloka_number_from_reference(reference: str) -> str:
    match = _REFERENCE_SHLOKA.search((reference or "").strip())
    return match.group(1) if match else ""


def mandala_from_reference(reference: str) -> str | None:
    number = shloka_number_from_reference(reference)
    if not number:
        return None
    mandala = number.split(".")[0]
    return f"Mandala {mandala}"


def values_equal(left, right) -> bool:
    if left == right:
        return True
    try:
        return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return False


def guru_field_changes(current: dict, incoming: dict) -> list[str]:
    return [field for field in GURU_FIELDS if field in incoming and not values_equal(current.get(field), incoming.get(field))]
