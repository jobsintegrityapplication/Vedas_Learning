"""Validate human-reviewed Sanskrit evaluation assets before any import/use.

This is a data-readiness check only. It never imports labels into the app and
never computes model accuracy from generated ASR/alignment output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

GURU_FIELDS = {
    "lesson_id", "source_audio", "word_order", "guru_approved_word", "start_ms", "end_ms",
    "text_review_status", "timing_review_status", "recitation_profile", "reviewer", "rights_status",
}
SAMPLE_FIELDS = {
    "sample_id", "audio_filename", "lesson_id", "recitation_profile", "consent_status",
    "human_transcript", "transcript_review_status", "speaker_code",
}
LABEL_FIELDS = {
    "event_id", "sample_id", "lesson_id", "word_order", "expected_word", "observed_word", "issue_category",
    "expected_phonetic_feature", "observed_phonetic_feature", "start_ms", "end_ms", "label",
    "confidence", "reviewer",
}
ISSUES = {
    "correct", "omission", "substitution", "insertion", "repetition", "vowel_length",
    "vowel_quality", "dental_retroflex", "aspiration", "voicing", "sibilant",
    "anusvara_visarga", "conjunct", "rhythm", "svara", "unclear",
}
LABEL_VALUES = {"correct", "incorrect", "uncertain"}
PII_PATTERNS = (re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b"), re.compile(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)"))


def _read_csv(path: Path, required: set[str], errors: list[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = required - set(reader.fieldnames or [])
            if missing:
                errors.append(f"{label}: missing columns: {', '.join(sorted(missing))}")
                return []
            rows = []
            for row in reader:
                cleaned = {key: (value or "").strip() for key, value in row.items() if key}
                if any(cleaned.values()):
                    rows.append(cleaned)
            return rows
    except OSError as exc:
        errors.append(f"{label}: cannot read {path}: {exc}")
        return []


def _audio_duration_ms(path: Path) -> int | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True, timeout=15,
        )
        return round(float(result.stdout.strip()) * 1000)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _safe_audio(root: Path, filename: str, errors: list[str], label: str,
                fallback_filename: str | None = None) -> tuple[Path | None, int | None]:
    candidate_name = Path(filename)
    if not filename or candidate_name.name != filename or filename in {".", ".."}:
        errors.append(f"{label}: audio_filename must be a plain filename, got {filename!r}")
        return None, None
    candidate = (root / filename).resolve()
    if (root.resolve() not in candidate.parents or not candidate.is_file()) and fallback_filename:
        fallback = Path(fallback_filename)
        if fallback.name != fallback_filename or fallback_filename in {".", ".."}:
            errors.append(f"{label}: invalid lesson audio fallback {fallback_filename!r}")
            return None, None
        candidate = (root / fallback_filename).resolve()
    if root.resolve() not in candidate.parents or not candidate.is_file():
        errors.append(f"{label}: audio file not found under supplied audio directory: {filename}")
        return None, None
    duration = _audio_duration_ms(candidate)
    if duration is None or duration <= 0:
        errors.append(f"{label}: duration could not be verified with ffprobe: {filename}")
        return candidate, None
    return candidate, duration


def _check_interval(row: dict[str, str], duration: int | None, errors: list[str], label: str) -> tuple[int | None, int | None]:
    try:
        start, end = int(row["start_ms"]), int(row["end_ms"])
    except (KeyError, ValueError):
        errors.append(f"{label}: start_ms and end_ms must be integers")
        return None, None
    if start < 0 or end <= start or (duration is not None and end > duration):
        errors.append(f"{label}: invalid interval {start}..{end} ms for duration {duration} ms")
    return start, end


def validate_bundle(guru_csv: Path, samples_csv: Path, labels_csv: Path,
                    guru_audio_dir: Path, learner_audio_dir: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    guru_rows = _read_csv(guru_csv, GURU_FIELDS, errors, "Guru review")
    samples = _read_csv(samples_csv, SAMPLE_FIELDS, errors, "Learner sample register")
    labels = _read_csv(labels_csv, LABEL_FIELDS, errors, "Learner labels")

    guru_seen: set[tuple[str, int]] = set()
    guru_audio: dict[str, tuple[Path | None, int | None]] = {}
    previous_end: dict[str, int] = {}
    for row in guru_rows:
        lesson, audio_name = row.get("lesson_id", ""), row.get("source_audio", "")
        try:
            order = int(row.get("word_order", ""))
        except ValueError:
            errors.append(f"Guru {lesson}: word_order must be an integer")
            continue
        key = (lesson, order)
        if not lesson or order < 1 or key in guru_seen:
            errors.append(f"Guru {lesson}: missing/duplicate lesson_id and word_order {order}")
        guru_seen.add(key)
        if row.get("text_review_status") != "approved" or not row.get("guru_approved_word"):
            errors.append(f"Guru {lesson} word {order}: transcript is not approved or approved word is blank")
        if row.get("timing_review_status") != "approved":
            errors.append(f"Guru {lesson} word {order}: timing is not approved")
        if row.get("recitation_profile") != "Common":
            errors.append(f"Guru {lesson} word {order}: expected Common profile")
        if row.get("rights_status") not in {"cleared", "public_domain"}:
            errors.append(f"Guru {lesson} word {order}: rights are not cleared")
        if not row.get("reviewer"):
            errors.append(f"Guru {lesson} word {order}: reviewer is missing")
        if audio_name not in guru_audio:
            # The original WhatsApp filenames are recorded in the review sheet,
            # while the app stores the same mapped clips as rigveda-NN.ogg.
            canonical_name = f"{lesson}.ogg" if re.fullmatch(r"rigveda-\d{2}", lesson) else None
            guru_audio[audio_name] = _safe_audio(
                guru_audio_dir, audio_name, errors, f"Guru {lesson}", canonical_name)
        _, duration = guru_audio[audio_name]
        start, end = _check_interval(row, duration, errors, f"Guru {lesson} word {order}")
        if start is not None and end is not None:
            if start < previous_end.get(lesson, 0):
                errors.append(f"Guru {lesson} word {order}: timing overlaps or is out of order")
            previous_end[lesson] = end

    sample_by_id: dict[str, dict[str, str]] = {}
    sample_audio: dict[str, tuple[Path | None, int | None]] = {}
    for row in samples:
        sid = row.get("sample_id", "")
        if not sid or sid in sample_by_id:
            errors.append(f"Learner samples: missing or duplicate sample_id {sid!r}")
            continue
        sample_by_id[sid] = row
        if row.get("recitation_profile") != "Common":
            errors.append(f"Learner {sid}: expected Common profile")
        if row.get("consent_status") != "confirmed":
            errors.append(f"Learner {sid}: consent is not confirmed")
        if row.get("transcript_review_status") != "approved" or not row.get("human_transcript"):
            errors.append(f"Learner {sid}: human transcript is not approved or is blank")
        if not row.get("speaker_code"):
            errors.append(f"Learner {sid}: anonymous speaker_code is required")
        if row.get("audio_filename") not in sample_audio:
            sample_audio[row.get("audio_filename", "")] = _safe_audio(
                learner_audio_dir, row.get("audio_filename", ""), errors, f"Learner {sid}")
        for field, value in row.items():
            if any(pattern.search(value) for pattern in PII_PATTERNS):
                errors.append(f"Learner {sid}: possible personal identifier in column {field}")

    issue_counts: Counter[str] = Counter()
    usable_label_count = 0
    seen_event_ids: set[str] = set()
    for index, row in enumerate(labels, 1):
        sid, issue = row.get("sample_id", ""), row.get("issue_category", "")
        event_id = row.get("event_id", "")
        if not event_id or event_id in seen_event_ids:
            errors.append(f"Learner label row {index}: event_id is missing or duplicated")
        seen_event_ids.add(event_id)
        if sid not in sample_by_id:
            errors.append(f"Learner label row {index}: unknown sample_id {sid!r}")
            continue
        if row.get("lesson_id") != sample_by_id[sid].get("lesson_id"):
            errors.append(f"Learner label row {index}: lesson does not match sample {sid}")
        if issue not in ISSUES:
            errors.append(f"Learner label row {index}: unsupported issue_category {issue!r}")
        else:
            issue_counts[issue] += 1
        if row.get("label") not in LABEL_VALUES:
            errors.append(f"Learner label row {index}: label must be correct, incorrect, or uncertain")
        else:
            if row["label"] != "uncertain" and issue != "unclear":
                usable_label_count += 1
        if issue not in {"correct", "omission", "insertion", "unclear"} and not (
            row.get("expected_phonetic_feature") and row.get("observed_phonetic_feature")
        ):
            errors.append(f"Learner label row {index}: sound contrast needs expected and observed feature values")
        try:
            confidence = float(row.get("confidence", ""))
            if not 0 <= confidence <= 1:
                raise ValueError
        except ValueError:
            errors.append(f"Learner label row {index}: confidence must be between 0 and 1")
        audio_path, duration = sample_audio.get(sample_by_id[sid].get("audio_filename", ""), (None, None))
        if audio_path:
            _check_interval(row, duration, errors, f"Learner label row {index}")
        if not row.get("reviewer"):
            errors.append(f"Learner label row {index}: reviewer is missing")

    if not samples:
        warnings.append("No learner recordings supplied")
    if not labels or usable_label_count == 0:
        warnings.append("No determinate reviewed sound labels; model accuracy cannot be measured")
    if not guru_rows:
        warnings.append("No Guru-reviewed word/timing rows supplied")

    audio_hashes = {}
    for entries in (guru_audio, sample_audio):
        for filename, (path, _) in entries.items():
            if path:
                audio_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "ready_for_human_reviewed_evaluation": not errors and bool(guru_rows) and bool(samples) and usable_label_count > 0,
        "production_imported": False,
        "counts": {"guru_word_rows": len(guru_rows), "learner_samples": len(sample_by_id),
                   "learner_label_rows": len(labels), "determinate_label_rows": usable_label_count},
        "label_categories": dict(sorted(issue_counts.items())),
        "audio_file_count": len(audio_hashes),
        "audio_sha256": dict(sorted(audio_hashes.items())),
        "errors": errors,
        "warnings": warnings,
        "limits": ["Readiness validation is not model evaluation.",
                   "This tool does not calculate ASR, alignment, pronunciation, or svara accuracy."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guru-csv", type=Path, required=True)
    parser.add_argument("--samples-csv", type=Path, required=True)
    parser.add_argument("--labels-csv", type=Path, required=True)
    parser.add_argument("--guru-audio-dir", type=Path, required=True)
    parser.add_argument("--learner-audio-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_bundle(args.guru_csv, args.samples_csv, args.labels_csv,
                             args.guru_audio_dir, args.learner_audio_dir)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["ready_for_human_reviewed_evaluation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
