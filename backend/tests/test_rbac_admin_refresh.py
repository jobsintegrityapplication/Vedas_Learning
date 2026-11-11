from app.models import Lesson, LessonAudit
from sqlalchemy import select
from tests.conftest import register_verified_tokens


def _register(client, email: str) -> dict:
    return register_verified_tokens(client, email)


def test_learner_cannot_access_admin(client):
    tokens = _register(client, "learner-rbac@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    denied = client.get("/api/admin/lessons", headers=headers)
    assert denied.status_code == 403


def test_admin_dashboard_and_guru_edit_guard(client, db):
    login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass123"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    dash = client.get("/api/admin/dashboard", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["lessons"] >= 1
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-01"))
    payload = {
        "slug": lesson.slug,
        "scripture_id": str(lesson.scripture_id),
        "title": lesson.title,
        "canonical_reference": lesson.canonical_reference,
        "sanskrit_text": "CHANGED-SANSKRIT",
        "meaning": lesson.meaning,
        "confirm_guru_edit": False,
    }
    blocked = client.put(f"/api/admin/lessons/{lesson.id}", headers=headers, json=payload)
    assert blocked.status_code == 409
    payload["confirm_guru_edit"] = True
    payload["edit_note"] = "Guru correction"
    allowed = client.put(f"/api/admin/lessons/{lesson.id}", headers=headers, json=payload)
    assert allowed.status_code == 200
    db.expire_all()
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-01"))
    assert lesson.sanskrit_text == "CHANGED-SANSKRIT"
    audit = db.scalars(select(LessonAudit).where(LessonAudit.lesson_id == lesson.id)).all()
    assert any(row.action == "guru_text_edit" for row in audit)
    lesson.sanskrit_text = "सत्येनोत्तभिता भूमिः सूर्येणोत्तभिता द्यौः ।\nऋतेनादित्यास्तिष्ठन्ति दिवि सोमो अधि श्रितः ॥"
    db.commit()


def test_refresh_and_logout(client):
    tokens = _register(client, "refresh@example.com")
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200
    assert me.json()["role"] == "learner"
    reused = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {new_access}"})
    again = client.post("/api/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]})
    assert again.status_code == 401


def test_profile_email_stays_verified_account(client):
    tokens = _register(client, "profile-email@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    saved = client.post(
        "/api/profile",
        headers=headers,
        json={"name": "Pat", "email": "attacker@example.com", "age": "21", "phone": "", "rashi": "", "nakshatra": "", "profession": ""},
    )
    assert saved.status_code == 200
    assert saved.json()["email"] == "profile-email@example.com"
    fetched = client.get("/api/profile", headers=headers)
    assert fetched.json()["email"] == "profile-email@example.com"


def test_chapters_list_and_admin_create(client):
    admin = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass123"}).json()
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    scriptures = client.get("/api/admin/scriptures", headers=admin_headers).json()
    rigveda = next(row for row in scriptures if row["slug"] == "rigveda")
    created = client.post(
        "/api/admin/chapters",
        headers=admin_headers,
        json={"scripture_id": rigveda["id"], "title": "Mandala 10", "sort_order": 1},
    )
    assert created.status_code == 200
    learner = _register(client, "chapter-user@example.com")
    listed = client.get("/api/scriptures/rigveda/chapters", headers={"Authorization": f"Bearer {learner['access_token']}"})
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Mandala 10"


def test_openapi_docs_available(client):
    docs = client.get("/openapi.json")
    assert docs.status_code == 200
    body = docs.json()
    assert "BearerAuth" in body["components"]["securitySchemes"]
    assert "/api/auth/refresh" in body["paths"]
    assert "/api/admin/dashboard" in body["paths"]


def test_health_does_not_require_database_query_shape(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"
