import csv
from pathlib import Path

from poc.validate_evaluation_bundle import validate_bundle


def _csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_reviewed_bundle_passes_readiness_without_claiming_model_evaluation(tmp_path, monkeypatch):
    guru_audio, learner_audio = tmp_path / "guru", tmp_path / "learner"
    guru_audio.mkdir()
    learner_audio.mkdir()
    (guru_audio / "guru.ogg").write_bytes(b"guru audio")
    (learner_audio / "attempt.ogg").write_bytes(b"learner audio")
    monkeypatch.setattr("poc.validate_evaluation_bundle._audio_duration_ms", lambda _path: 5000)

    guru_csv = _csv(tmp_path / "guru.csv", [
        "lesson_id", "source_audio", "word_order", "candidate_source_word", "guru_approved_word",
        "start_ms", "end_ms", "text_review_status", "timing_review_status", "recitation_profile",
        "reviewer", "rights_status",
    ], [{"lesson_id": "rigveda-01", "source_audio": "guru.ogg", "word_order": "1",
         "guru_approved_word": "गुरु", "start_ms": "100", "end_ms": "800",
         "text_review_status": "approved", "timing_review_status": "approved",
         "recitation_profile": "Common", "reviewer": "reviewer-1", "rights_status": "cleared"}])
    samples_csv = _csv(tmp_path / "samples.csv", [
        "sample_id", "audio_filename", "lesson_id", "recitation_profile", "consent_status",
        "human_transcript", "transcript_review_status", "speaker_code",
    ], [{"sample_id": "sample-1", "audio_filename": "attempt.ogg", "lesson_id": "rigveda-01",
         "recitation_profile": "Common", "consent_status": "confirmed", "human_transcript": "गुरु",
         "transcript_review_status": "approved", "speaker_code": "anon-1"}])
    labels_csv = _csv(tmp_path / "labels.csv", [
        "event_id", "sample_id", "lesson_id", "word_order", "expected_word", "observed_word", "issue_category",
        "expected_phonetic_feature", "observed_phonetic_feature", "start_ms", "end_ms", "label",
        "confidence", "reviewer",
    ], [{"event_id": "event-1", "sample_id": "sample-1", "lesson_id": "rigveda-01", "word_order": "1",
         "expected_word": "गुरु", "observed_word": "गुरु", "issue_category": "correct",
         "start_ms": "100", "end_ms": "900", "label": "correct", "confidence": "0.95",
         "reviewer": "reviewer-1"}])

    report = validate_bundle(guru_csv, samples_csv, labels_csv, guru_audio, learner_audio)
    assert report["ready_for_human_reviewed_evaluation"] is True
    assert report["production_imported"] is False
    assert report["counts"]["determinate_label_rows"] == 1
    assert len(report["audio_sha256"]) == 2
    assert "does not calculate" in report["limits"][1]


def test_bundle_fails_closed_for_unconfirmed_consent_and_path_traversal(tmp_path, monkeypatch):
    guru_audio, learner_audio = tmp_path / "guru", tmp_path / "learner"
    guru_audio.mkdir()
    learner_audio.mkdir()
    (guru_audio / "guru.ogg").write_bytes(b"guru audio")
    (tmp_path / "outside.ogg").write_bytes(b"outside")
    monkeypatch.setattr("poc.validate_evaluation_bundle._audio_duration_ms", lambda _path: 5000)
    guru_csv = _csv(tmp_path / "guru.csv", [
        "lesson_id", "source_audio", "word_order", "guru_approved_word", "start_ms", "end_ms",
        "text_review_status", "timing_review_status", "recitation_profile", "reviewer", "rights_status",
    ], [{"lesson_id": "rigveda-01", "source_audio": "guru.ogg", "word_order": "1",
         "guru_approved_word": "गुरु", "start_ms": "100", "end_ms": "800",
         "text_review_status": "approved", "timing_review_status": "approved",
         "recitation_profile": "Common", "reviewer": "reviewer-1", "rights_status": "cleared"}])
    samples_csv = _csv(tmp_path / "samples.csv", [
        "sample_id", "audio_filename", "lesson_id", "recitation_profile", "consent_status",
        "human_transcript", "transcript_review_status", "speaker_code",
    ], [{"sample_id": "sample-1", "audio_filename": "../outside.ogg", "lesson_id": "rigveda-01",
         "recitation_profile": "Common", "consent_status": "pending", "human_transcript": "गुरु",
         "transcript_review_status": "approved", "speaker_code": "anon-1"}])
    labels_csv = _csv(tmp_path / "labels.csv", [
        "event_id", "sample_id", "lesson_id", "word_order", "expected_word", "observed_word", "issue_category",
        "expected_phonetic_feature", "observed_phonetic_feature", "start_ms", "end_ms", "label",
        "confidence", "reviewer",
    ], [])
    report = validate_bundle(guru_csv, samples_csv, labels_csv, guru_audio, learner_audio)
    assert report["ready_for_human_reviewed_evaluation"] is False
    assert any("consent is not confirmed" in issue for issue in report["errors"])
    assert any("plain filename" in issue for issue in report["errors"])
