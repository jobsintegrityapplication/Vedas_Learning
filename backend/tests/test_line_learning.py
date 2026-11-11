import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.api.lessons import CompleteLineIn, complete_line, get_lesson
from app.api.activity import LearningEventIn, record_learning_event
from app.models import Evaluation, Lesson, Recording, User
from sqlalchemy import select


def _add_accepted_word_match(db, user, lesson_id, line_index, match_percent):
    recording = Recording(
        user_id=user.id, lesson_id=lesson_id, line_index=line_index,
        recitation_profile="Kanchi", storage_key=f"learner/test/{uuid4()}.wav",
        content_type="audio/wav", original_filename="attempt.wav", kind="learner", byte_size=64,
    )
    db.add(recording)
    db.flush()
    accepted = match_percent >= 90
    db.add(Evaluation(
        recording_id=recording.id, status="completed", word_accuracy_status="completed",
        report={
            "accepted": accepted,
            "reference_audio_status": "available",
            "word_accuracy": {
                "match_percent": match_percent,
                "pass_threshold_percent": 90,
                "meets_word_threshold": accepted,
            },
        },
    ))
    db.commit()


def test_all_nine_lessons_require_90_percent_word_match_before_line_progress(db):
    user = db.scalar(select(User).limit(1))
    assert user is not None
    source = json.loads((Path(__file__).resolve().parents[2] / "content" / "rigveda_lessons.json").read_text(encoding="utf-8"))
    for item in source:
        payload = get_lesson(item['id'], user, db)
        expected = [line.strip() for line in item["sanskrit"].splitlines() if line.strip()]
        assert payload["lines"] == expected
        assert payload["svara_status"] == "unavailable_not_in_source"
        assert payload["completed_line_indices"] == []
        lesson = db.scalar(select(Lesson).where(Lesson.slug == item['id']))
        assert lesson is not None
        with pytest.raises(HTTPException) as blocked:
            complete_line(item['id'], CompleteLineIn(line_index=0), user, db)
        assert blocked.value.status_code == 409
        _add_accepted_word_match(db, user, lesson.id, 0, 89.99)
        with pytest.raises(HTTPException) as below_threshold:
            complete_line(item['id'], CompleteLineIn(line_index=0), user, db)
        assert below_threshold.value.status_code == 409
        if len(expected) > 1:
            _add_accepted_word_match(db, user, lesson.id, 1, 90.0)
            with pytest.raises(HTTPException) as out_of_order:
                complete_line(item['id'], CompleteLineIn(line_index=1), user, db)
            assert out_of_order.value.status_code == 409
        for index in range(len(expected)):
            _add_accepted_word_match(db, user, lesson.id, index, 90.0)
            done = complete_line(item['id'], CompleteLineIn(line_index=index), user, db)
            assert done["policy"] == "90_percent_word_match"
        final = get_lesson(item['id'], user, db)
        assert final["completed_line_indices"] == list(range(len(expected)))


def test_lesson_completion_cannot_be_forged_without_passed_lines(db):
    user = db.scalar(select(User).limit(1))
    assert user is not None
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-01"))
    assert lesson is not None
    with pytest.raises(HTTPException) as blocked:
        record_learning_event(LearningEventIn(event_type="lesson_completed", lesson_slug=lesson.slug), user, db)
    assert blocked.value.status_code == 409


def test_authenticated_e2e_word_match_unlocks_lines_and_lesson(client, db):
    from tests.conftest import register_verified_tokens

    tokens = register_verified_tokens(client, "lesson-gate-e2e@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user = db.scalar(select(User).where(User.email == "lesson-gate-e2e@example.com"))
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-01"))
    assert user is not None and lesson is not None
    line_count = len([line for line in lesson.sanskrit_text.splitlines() if line.strip()])

    blocked = client.post(
        f"/api/lessons/{lesson.slug}/lines/complete", headers=headers, json={"line_index": 0}
    )
    assert blocked.status_code == 409
    forged_lesson_complete = client.post(
        "/api/activity", headers=headers,
        json={"event_type": "lesson_completed", "lesson_slug": lesson.slug},
    )
    assert forged_lesson_complete.status_code == 409

    _add_accepted_word_match(db, user, lesson.id, 0, 89.99)
    below_threshold = client.post(
        f"/api/lessons/{lesson.slug}/lines/complete", headers=headers, json={"line_index": 0}
    )
    assert below_threshold.status_code == 409

    for line_index in range(line_count):
        _add_accepted_word_match(db, user, lesson.id, line_index, 90.0)
        completed_line = client.post(
            f"/api/lessons/{lesson.slug}/lines/complete", headers=headers,
            json={"line_index": line_index},
        )
        assert completed_line.status_code == 200, completed_line.text

    completed_lesson = client.post(
        "/api/activity", headers=headers,
        json={"event_type": "lesson_completed", "lesson_slug": lesson.slug},
    )
    assert completed_lesson.status_code == 200, completed_lesson.text
    assert completed_lesson.json()["lesson_completed"] is True


def test_audio_candidates_are_provenance_tracked_and_never_canonical_by_default():
    manifest = json.loads((Path(__file__).resolve().parents[2] / "content" / "rigveda_review_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["lessons"]) == 9
    for lesson in manifest["lessons"]:
        assert lesson["audio_candidates"]
        for candidate in lesson["audio_candidates"]:
            assert candidate["url"].startswith("https://")
            assert candidate["publisher"]
            assert candidate["attribution"]
            assert candidate["license"]
            assert candidate["verification_status"] == "candidate_unverified_pending_guru"
            assert candidate["canonical"] is False
