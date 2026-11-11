import io
import os
import wave
from uuid import UUID

from app.core.config import get_settings
from app.models import Evaluation, GuruReferenceAudio, Recording
from app.services.audio_validation import AudioValidationError, inspect_audio
from app.services.audio_preprocess import preprocess_audio
from app.services.engines.base import TranscriptResult
from app.services.engines.none import NonePronunciationEngine
from app.services.content_integrity import tokenize_guru_text
from app.services.evaluation import UNAVAILABLE_SVARA, evaluate_hypothesis
from app.services.pipeline import run_evaluation_pipeline
from app.services.storage import get_bytes
from sqlalchemy import select
from tests.audio_samples import FIXTURE_DIR, make_wav_bytes, write_sample_recordings
from tests.conftest import register_verified_tokens


def _learner(client) -> dict:
    tokens = register_verified_tokens(client, "audio-learner@example.com")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _admin(client) -> dict:
    login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _enable_scripted():
    os.environ["EVALUATION_ENGINE"] = "scripted"
    os.environ["EVALUATION_ENGINE_VERSION"] = "1"
    os.environ["EVALUATION_FIXTURE_DIR"] = str(FIXTURE_DIR)
    get_settings.cache_clear()


def test_tokenize_rigveda_02_matches_fixtures(db):
    from app.models import Lesson

    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-02"))
    tokens = tokenize_guru_text(lesson.sanskrit_text)
    assert tokens[0] == "संगच्छध्वं"
    assert "वो" in tokens


def test_wav_validation_rejects_non_audio():
    write_sample_recordings()
    inspect_audio(make_wav_bytes(), "ok.wav", "audio/wav")
    try:
        inspect_audio(b"not-an-audio-file-at-all-padded-xxxx", "fake.wav", "audio/wav")
        assert False, "expected validation error"
    except AudioValidationError:
        pass


def test_ffmpeg_normalization_writes_real_wav_duration(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "audio_sample_rate", 22050)
    source = make_wav_bytes(duration_ms=1000, sample_rate=16000)
    normalized = preprocess_audio(source, "source.wav", "audio/wav")
    assert normalized.status == "normalized"
    assert normalized.inspection.sample_rate == 22050
    assert normalized.inspection.duration_ms == 1000
    with wave.open(io.BytesIO(normalized.data), "rb") as wav:
        assert wav.getnframes() == 22050


def test_pipeline_without_engine_does_not_invent_scores():
    wav = make_wav_bytes()
    report = run_evaluation_pipeline(
        learner_bytes=wav,
        learner_filename="complete.wav",
        learner_content_type="audio/wav",
        learner_storage_key="learner/test/complete.wav",
        guru_text="संगच्छध्वं संवदध्वं",
        guru_bytes=None,
        guru_filename=None,
        guru_content_type=None,
        guru_storage_key=None,
        lesson_slug="rigveda-02",
    )
    assert report["engine_status"] == "not_configured"
    assert report["word_accuracy"]["status"] == "unavailable"
    assert report["word_accuracy"]["alignment"] is None
    assert report["pronunciation"]["scores"] is None
    assert report["svara"]["status"] == "unavailable"
    assert UNAVAILABLE_SVARA in report["svara"]["reason"]
    assert "score" not in report


def test_scripted_samples_detect_omission_and_substitution():
    write_sample_recordings()
    _enable_scripted()
    try:
        reference = "संगच्छध्वं संवदध्वं सं वो मनांसि जानताम् ।"
        omitted = run_evaluation_pipeline(
            learner_bytes=make_wav_bytes(),
            learner_filename="omission.wav",
            learner_content_type="audio/wav",
            learner_storage_key="learner/test/omission.wav",
            guru_text=reference,
            guru_bytes=None,
            guru_filename=None,
            guru_content_type=None,
            guru_storage_key=None,
            lesson_slug="rigveda-02",
        )
        assert omitted["word_accuracy"]["status"] == "completed"
        assert omitted["word_accuracy"]["evidence"]["omissions"] == ["वो"]
        assert omitted["word_accuracy"]["match_percent"] < 95
        assert omitted["accepted"] is False
        assert omitted["pronunciation"]["status"] == "unavailable"
        assert omitted["svara"]["status"] == "unavailable"

        substituted = run_evaluation_pipeline(
            learner_bytes=make_wav_bytes(),
            learner_filename="substitution.wav",
            learner_content_type="audio/wav",
            learner_storage_key="learner/test/substitution.wav",
            guru_text=reference,
            guru_bytes=None,
            guru_filename=None,
            guru_content_type=None,
            guru_storage_key=None,
            lesson_slug="rigveda-02",
        )
        assert substituted["word_accuracy"]["evidence"]["substitutions"] == [{"expected": "वो", "actual": "मो"}]
    finally:
        os.environ["EVALUATION_ENGINE"] = "none"
        get_settings.cache_clear()


def test_upload_stores_namespaces_separately(client, db):
    write_sample_recordings()
    _enable_scripted()
    try:
        admin = _admin(client)
        learner = _learner(client)
        lesson = client.get("/api/scriptures/rigveda/lessons", headers=learner).json()
        target = next(row for row in lesson if row["slug"] == "rigveda-02")
        guru_wav = (FIXTURE_DIR / "guru_reference.wav").read_bytes()
        uploaded = client.post(
            f"/api/admin/lessons/{target['id']}/reference-audio",
            headers=admin,
            files={"audio": ("guru_reference.wav", guru_wav, "audio/wav")},
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["namespace"] == "guru"
        assert uploaded.json()["storage_key"].startswith("guru/")
        guru_row = db.scalar(select(GuruReferenceAudio).where(GuruReferenceAudio.lesson_id == UUID(target["id"])))
        assert guru_row is not None
        assert get_bytes(guru_row.storage_key)[0] == guru_wav

        learner_wav = (FIXTURE_DIR / "omission.wav").read_bytes()
        result = client.post(
            "/api/recordings/evaluate",
            headers=learner,
            data={"lesson_id": "rigveda-02"},
            files={"audio": ("omission.wav", learner_wav, "audio/wav")},
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["evaluation_status"] == "unavailable"
        assert body["recitation_profile"] == "Kanchi"
        assert body["report"]["reference_text_status"] == "unavailable"
        assert "learner_key" not in (body["report"]["storage"] or {})
        assert body["report"]["storage"]["guru_audio_present"] is False
        assert body["report"]["word_accuracy"]["status"] == "unavailable"
        assert body["svara_status"] == "unavailable"
        assert body["report"]["pronunciation"]["scores"] is None
        recording = db.scalar(select(Recording).where(Recording.kind == "learner"))
        assert recording.storage_key.startswith("learner/") and "/Kanchi/" in recording.storage_key
        assert recording.recitation_profile == "Kanchi"
        assert recording.container == "wav"

        pronunciation = client.post(
            "/api/recordings/evaluate",
            headers=learner,
            data={"lesson_id": "rigveda-02", "recitation_profile": "Sringeri", "mantra_reference": "RV.02.001.01"},
            files={"audio": ("pronunciation.wav", (FIXTURE_DIR / "pronunciation.wav").read_bytes(), "audio/wav")},
        )
        assert pronunciation.status_code == 200
        report = pronunciation.json()["report"]
        assert report["recitation_profile"] == "Sringeri"
        assert report["reference_text_status"] == "unavailable"
        assert report["pronunciation"]["status"] == "unavailable"
        assert report["pronunciation"]["phonetic_evidence"] == []
        assert report["pronunciation"]["scores"] is None
        sringeri_recording = db.scalar(select(Recording).where(Recording.recitation_profile == "Sringeri"))
        assert sringeri_recording is not None and "/Sringeri/" in sringeri_recording.storage_key

        common = client.post(
            "/api/recordings/evaluate",
            headers=learner,
            data={"lesson_id": "rigveda-02", "recitation_profile": "Common", "mantra_reference": "RV.02.001.01"},
            files={"audio": ("common.wav", (FIXTURE_DIR / "pronunciation.wav").read_bytes(), "audio/wav")},
        )
        assert common.status_code == 200, common.text
        assert common.json()["recitation_profile"] == "Common"
        assert common.json()["report"]["reference_text_status"] == "unavailable"
        common_recording = db.scalar(select(Recording).where(Recording.recitation_profile == "Common"))
        assert common_recording is not None and "/Common/" in common_recording.storage_key

        rejected = client.post(
            "/api/recordings/evaluate",
            headers=learner,
            data={"lesson_id": "rigveda-02"},
            files={"audio": ("complete.wav", b"this is not wav data padded to sixty-four bytes!!!!!!", "audio/wav")},
        )
        assert rejected.status_code == 400
    finally:
        os.environ["EVALUATION_ENGINE"] = "none"
        get_settings.cache_clear()


def test_unconfigured_asr_returns_inline_unavailable_instead_of_queuing(client, db, monkeypatch):
    import app.api.recordings as recordings_api

    settings = get_settings()
    monkeypatch.setattr(settings, "audio_store", "s3")
    monkeypatch.setattr(recordings_api, "engine_is_configured", lambda: False)
    monkeypatch.setattr(recordings_api, "put_bytes", lambda *_args, **_kwargs: None)

    def unavailable_inline(recording_id):
        evaluation = db.scalar(select(Evaluation).where(Evaluation.recording_id == UUID(recording_id)))
        evaluation.status = "unavailable"
        evaluation.engine_id = "none"
        evaluation.engine_version = "0"
        evaluation.word_accuracy_status = "unavailable"
        evaluation.pronunciation_status = "unavailable"
        evaluation.svara_status = "unavailable"
        evaluation.report = {"engine_status": "not_configured", "word_accuracy": {"status": "unavailable"}, "storage": {}}
        evaluation.message = "No Sanskrit ASR engine is configured."
        db.flush()

    monkeypatch.setattr(recordings_api, "evaluate_recording", unavailable_inline)
    headers = _learner(client)
    result = client.post(
        "/api/recordings/evaluate",
        headers=headers,
        data={"lesson_id": "rigveda-02"},
        files={"audio": ("short-shloka.wav", make_wav_bytes(), "audio/wav")},
    )
    assert result.status_code == 200, result.text
    assert result.json()["queued"] is False
    assert result.json()["evaluation_status"] == "unavailable"
    assert result.json()["engine_status"] == "not_configured"


def test_hypothesis_alignment_helper_stays_honest_without_engine():
    os.environ["EVALUATION_ENGINE"] = "none"
    get_settings.cache_clear()
    report = evaluate_hypothesis(["a", "b"], ["a"])
    assert report["engine_status"] == "not_configured"
    assert report["word_accuracy"]["status"] == "unavailable"


def test_pipeline_accepts_90_percent_word_match_without_pronunciation_score(monkeypatch):
    import app.services.pipeline as pipeline
    from app.services.engines.none import NonePronunciationEngine

    class ValidatedFixtureEngine:
        engine_id = "validated_fixture"
        version = "test"

        def __init__(self, substitutions):
            self.substitutions = substitutions

        def transcribe(self, context):
            tokens = context.reference_tokens[:-self.substitutions] + [f"substituted-{i}" for i in range(self.substitutions)]
            return TranscriptResult(status="completed", reason="Test transcript", tokens=tokens)

    monkeypatch.setenv("EVALUATION_ENGINE", "scripted")
    monkeypatch.setenv("WORD_MATCH_PASS_THRESHOLD_PERCENT", "90")
    get_settings.cache_clear()
    monkeypatch.setattr(pipeline, "engine_is_configured", lambda: True)
    monkeypatch.setattr(pipeline, "get_pronunciation_engine", NonePronunciationEngine)
    reference = [f"word-{index}" for index in range(20)]
    monkeypatch.setattr(pipeline, "get_transcription_engine", lambda: ValidatedFixtureEngine(2))
    no_guru_audio = pipeline.run_evaluation_pipeline(
        learner_bytes=make_wav_bytes(), learner_filename="test.wav", learner_content_type="audio/wav",
        learner_storage_key="learner/test.wav", guru_text="", guru_bytes=None, guru_filename=None,
        guru_content_type=None, guru_storage_key=None, lesson_slug="test", reference_tokens=reference,
    )
    assert no_guru_audio["word_accuracy"]["match_percent"] == 90.0
    assert no_guru_audio["accepted"] is False
    assert "Guru reference audio is unavailable" in no_guru_audio["acceptance_reason"]

    passed = pipeline.run_evaluation_pipeline(
        learner_bytes=make_wav_bytes(), learner_filename="test.wav", learner_content_type="audio/wav",
        learner_storage_key="learner/test.wav", guru_text="", guru_bytes=make_wav_bytes(), guru_filename="guru.wav",
        guru_content_type="audio/wav", guru_storage_key="guru/test.wav", lesson_slug="test", reference_tokens=reference,
    )
    assert passed["word_accuracy"]["match_percent"] == 90.0
    assert passed["accepted"] is True
    assert passed["pronunciation"]["status"] == "unavailable"

    monkeypatch.setattr(pipeline, "get_transcription_engine", lambda: ValidatedFixtureEngine(3))
    failed = pipeline.run_evaluation_pipeline(
        learner_bytes=make_wav_bytes(), learner_filename="test.wav", learner_content_type="audio/wav",
        learner_storage_key="learner/test.wav", guru_text="", guru_bytes=make_wav_bytes(), guru_filename="guru.wav",
        guru_content_type="audio/wav", guru_storage_key="guru/test.wav", lesson_slug="test", reference_tokens=reference,
    )
    assert failed["word_accuracy"]["match_percent"] == 85.0
    assert failed["accepted"] is False
    get_settings.cache_clear()


def test_unreviewed_development_diagnostic_reports_candidate_match_but_never_accepts(monkeypatch):
    import app.services.pipeline as pipeline
    from app.services.engines.none import NonePronunciationEngine, NoneSvaraEngine

    class CandidateTranscriptEngine:
        engine_id = "test_asr"
        version = "1"

        def transcribe(self, context):
            return TranscriptResult(status="completed", reason="candidate ASR", tokens=context.reference_tokens)

    monkeypatch.setattr(pipeline, "get_transcription_engine", CandidateTranscriptEngine)
    monkeypatch.setattr(pipeline, "get_pronunciation_engine", NonePronunciationEngine)
    monkeypatch.setattr(pipeline, "get_svara_engine", NoneSvaraEngine)
    monkeypatch.setattr(pipeline, "engine_is_configured", lambda: True)
    report = pipeline.run_evaluation_pipeline(
        learner_bytes=make_wav_bytes(), learner_filename="replayed-guru.wav", learner_content_type="audio/wav",
        learner_storage_key="learner/diagnostic.wav", guru_text="", guru_bytes=make_wav_bytes(),
        guru_filename="guru.wav", guru_content_type="audio/wav", guru_storage_key="guru/reference.wav",
        lesson_slug="rigveda-01", recitation_profile="Common", reference_tokens=["गुरु", "नमः"],
        reference_is_reviewed=False,
    )
    assert report["diagnostic_only"] is True
    assert report["reference_text_status"] == "development_candidate_unreviewed"
    assert report["word_accuracy"]["match_percent"] == 100.0
    assert report["accepted"] is False
    assert "cannot be accepted or unlock progress" in report["acceptance_reason"]


def test_pipeline_aligns_guru_and_student_separately_for_timing_diagnostics(monkeypatch):
    import app.services.pipeline as pipeline
    from app.services.engines.none import NonePronunciationEngine, NoneSvaraEngine, NoneTranscriptionEngine

    seen = []

    class FakeAligner:
        engine_id = "test_aligner"
        version = "1"

        def forced_align(self, context, reference_tokens):
            seen.append((context.learner_filename, context.learner_audio.status))
            return {
                "status": "completed", "engine_id": self.engine_id, "engine_version": self.version,
                "words": [
                    {"word_order": 1, "word": "गुरु", "start_ms": 100, "end_ms": 350, "confidence": 0.9},
                    {"word_order": 2, "word": "नमः", "start_ms": 500, "end_ms": 800, "confidence": 0.9},
                ],
            }

    monkeypatch.setattr(pipeline, "get_transcription_engine", NoneTranscriptionEngine)
    monkeypatch.setattr(pipeline, "get_pronunciation_engine", NonePronunciationEngine)
    monkeypatch.setattr(pipeline, "get_svara_engine", NoneSvaraEngine)
    monkeypatch.setattr(pipeline, "get_alignment_engine", FakeAligner)
    monkeypatch.setattr(pipeline, "alignment_engine_is_configured", lambda: True)
    monkeypatch.setattr(pipeline, "engine_is_configured", lambda: False)

    report = pipeline.run_evaluation_pipeline(
        learner_bytes=make_wav_bytes(duration_ms=1000), learner_filename="student.wav", learner_content_type="audio/wav",
        learner_storage_key="learner/test.wav", guru_text="", guru_bytes=make_wav_bytes(duration_ms=1000),
        guru_filename="guru.wav", guru_content_type="audio/wav", guru_storage_key="guru/test.wav",
        lesson_slug="test", reference_tokens=["गुरु", "नमः"],
    )
    assert seen == [("student.wav", "normalized"), ("guru.wav", "normalized")]
    comparison = report["guru_student_timing_comparison"]
    assert comparison["status"] == "candidate_only"
    assert comparison["score"] is None
    assert len(comparison["words"]) == 2
    get_settings.cache_clear()
