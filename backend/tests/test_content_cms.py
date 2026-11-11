import json
from pathlib import Path

from sqlalchemy import select

from app.models import Lesson, LessonAudit, LessonVersion
from app.services.content_cms import import_rigveda_lessons
from app.services.content_integrity import fingerprint
from tests.conftest import register_verified_tokens


SOURCE = Path(__file__).resolve().parents[2] / "content" / "rigveda_lessons.json"


def _admin_headers(client) -> dict:
    login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _learner_headers(client) -> dict:
    tokens = register_verified_tokens(client, "cms-learner@example.com")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_import_copies_rigveda_wording_exactly(db):
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    first = source[0]
    lesson = db.scalar(select(Lesson).where(Lesson.slug == first["id"]))
    assert lesson is not None
    assert lesson.sanskrit_text == first["sanskrit"]
    assert lesson.meaning == first["meaning"]
    assert lesson.canonical_reference == first["reference"]
    assert lesson.title == first["title"]
    assert lesson.daily_application == first["dailyApplication"]
    assert lesson.transliteration == ""
    assert lesson.translation == ""
    assert lesson.shloka_number == "10.85.1"
    assert lesson.is_published is True
    versions = db.scalars(select(LessonVersion).where(LessonVersion.lesson_id == lesson.id)).all()
    assert len(versions) == 1
    assert versions[0].sanskrit_text == first["sanskrit"]


def test_reimport_never_rewrites_database_text(db):
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-01"))
    original_sanskrit = lesson.sanskrit_text
    lesson.sanskrit_text = "NOT-IN-SOURCE"
    lesson.content_fingerprint = fingerprint("NOT-IN-SOURCE", lesson.meaning)
    db.commit()
    result = import_rigveda_lessons(db, SOURCE)
    db.refresh(lesson)
    assert lesson.sanskrit_text == "NOT-IN-SOURCE"
    assert result["refused_overwrite"] >= 1
    lesson.sanskrit_text = original_sanskrit
    lesson.content_fingerprint = fingerprint(original_sanskrit, lesson.meaning)
    db.commit()


def test_learner_cannot_publish_or_import(client):
    headers = _learner_headers(client)
    assert client.post("/api/admin/content/import-rigveda", headers=headers).status_code == 403
    lesson_id = client.get("/api/scriptures/rigveda/lessons", headers=headers).json()[0]["id"]
    denied = client.post(f"/api/admin/lessons/{lesson_id}/publish", headers=headers, json={"note": "no"})
    assert denied.status_code == 403


def test_admin_draft_is_hidden_until_publish(client, db):
    headers = _admin_headers(client)
    scripture_id = next(row["id"] for row in client.get("/api/admin/scriptures", headers=headers).json() if row["slug"] == "rigveda")
    created = client.post(
        "/api/admin/lessons",
        headers=headers,
        json={
            "slug": "rigveda-draft-test",
            "scripture_id": scripture_id,
            "title": "Draft shloka",
            "canonical_reference": "Rigveda 10.0.0",
            "sanskrit_text": "गुरुदत्तम्",
            "meaning": "Guru supplied meaning",
            "translation": "Guru supplied translation",
            "transliteration": "gurudattam",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["is_published"] is False
    lesson_id = created.json()["id"]
    learner = _learner_headers(client)
    listed = client.get("/api/scriptures/rigveda/lessons", headers=learner)
    slugs = [row["slug"] for row in listed.json()]
    assert "rigveda-draft-test" not in slugs
    published = client.post(f"/api/admin/lessons/{lesson_id}/publish", headers=headers, json={"note": "Guru approved"})
    assert published.status_code == 200
    listed = client.get("/api/scriptures/rigveda/lessons", headers=learner)
    assert "rigveda-draft-test" in [row["slug"] for row in listed.json()]
    detail = next(row for row in listed.json() if row["slug"] == "rigveda-draft-test")
    assert detail["sanskrit"] == "गुरुदत्तम्"
    assert detail["translation"] == "Guru supplied translation"
    audits = client.get(f"/api/admin/lessons/{lesson_id}/audits", headers=headers)
    assert audits.status_code == 200
    assert any(row["action"] == "publish" for row in audits.json())
    unpublished = client.post(f"/api/admin/lessons/{lesson_id}/unpublish", headers=headers, json={"note": "hide"})
    assert unpublished.status_code == 200
    listed = client.get("/api/scriptures/rigveda/lessons", headers=learner)
    assert "rigveda-draft-test" not in [row["slug"] for row in listed.json()]


def test_guru_edit_creates_new_version_and_audit(client, db):
    headers = _admin_headers(client)
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-02"))
    original = lesson.sanskrit_text
    payload = {
        "slug": lesson.slug,
        "scripture_id": str(lesson.scripture_id),
        "title": lesson.title,
        "canonical_reference": lesson.canonical_reference,
        "sanskrit_text": "CHANGED-BY-ADMIN",
        "meaning": lesson.meaning,
        "confirm_guru_edit": False,
        "edit_note": "",
    }
    blocked = client.put(f"/api/admin/lessons/{lesson.id}", headers=headers, json=payload)
    assert blocked.status_code == 409
    payload["confirm_guru_edit"] = True
    payload["edit_note"] = "Guru correction of a typo"
    allowed = client.put(f"/api/admin/lessons/{lesson.id}", headers=headers, json=payload)
    assert allowed.status_code == 200
    assert allowed.json()["version_number"] == 2
    versions = client.get(f"/api/admin/lessons/{lesson.id}/versions", headers=headers).json()
    assert [row["version_number"] for row in versions] == [1, 2]
    assert versions[0]["sanskrit_text"] == original
    assert versions[1]["sanskrit_text"] == "CHANGED-BY-ADMIN"
    restore = client.post(
        f"/api/admin/lessons/{lesson.id}/versions/1/restore",
        headers=headers,
        json={"confirm_guru_edit": True, "edit_note": "Restore Guru source wording"},
    )
    assert restore.status_code == 200
    db.expire_all()
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-02"))
    assert lesson.sanskrit_text == original
    audits = db.scalars(select(LessonAudit).where(LessonAudit.lesson_id == lesson.id)).all()
    assert {row.action for row in audits} >= {"import", "guru_text_edit", "restore"}
