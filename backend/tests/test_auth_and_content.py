from sqlalchemy import select
from urllib.parse import parse_qs, urlparse

from app.models import Lesson
from app.services.content_integrity import fingerprint
from app.services.seed import seed_guru_lessons
from tests.conftest import register_verified_tokens


def test_register_verify_login_and_profile(client):
    register = client.post("/api/auth/register", json={"email": "learner@example.com"})
    assert register.status_code == 200, register.text
    assert register.json()["email_sent"] is True
    assert "access_token" not in register.json()
    blocked = client.post("/api/auth/login", json={"identifier": "learner@example.com", "password": "password1"})
    assert blocked.status_code == 403
    token = parse_qs(urlparse(register.json()["demo_verification_url"]).query)["signup_token"][0]
    assert client.post("/api/auth/verify-email-link", json={"email": "learner@example.com", "verification_token": "x" * 43}).status_code == 400
    verified = client.post("/api/auth/verify-email-link", json={"email": "learner@example.com", "verification_token": token})
    assert verified.status_code == 200
    assert verified.json()["verified"] is True
    completed = client.post(
        "/api/auth/complete-signup",
        json={
            "email": "learner@example.com",
            "verification_token": token,
            "full_name": "Learner Test",
            "username": "learner.test",
            "phone": "9876543210",
            "password": "password1",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["username"] == "learner.test"
    assert completed.json().get("access_token")
    by_email = client.post("/api/auth/login", json={"identifier": "learner@example.com", "password": "password1"})
    assert by_email.status_code == 200
    by_phone = client.post("/api/auth/login", json={"identifier": "9876543210", "password": "password1"})
    assert by_phone.status_code == 200
    reused = client.post(
        "/api/auth/complete-signup",
        json={"email": "learner@example.com", "verification_token": token, "full_name": "Learner Test", "password": "password1"},
    )
    assert reused.status_code == 409
    token = completed.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    saved = client.post(
        "/api/profile",
        headers=headers,
        json={"name": "Learner", "email": "learner@example.com", "age": "30", "phone": "", "rashi": "", "nakshatra": "Ashwini", "gotra": "Bharadwaja", "preferred_language": "kn", "profession": "Teacher"},
    )
    assert saved.status_code == 200
    assert saved.json()["gotra"] == "Bharadwaja"
    assert saved.json()["preferred_language"] == "kn"
    fetched_profile = client.get("/api/profile", headers=headers)
    assert fetched_profile.json()["gotra"] == "Bharadwaja"
    assert fetched_profile.json()["preferred_language"] == "kn"
    language_saved = client.post("/api/profile/preferred-language", headers=headers, json={"preferred_language": "hi"})
    assert language_saved.status_code == 200
    assert language_saved.json()["preferred_language"] == "hi"
    unsupported_language = client.post(
        "/api/profile/preferred-language", headers=headers, json={"preferred_language": "xx"}
    )
    assert unsupported_language.status_code == 422
    scriptures = client.get("/api/scriptures", headers=headers)
    assert scriptures.status_code == 200
    titles = [row["title"] for row in scriptures.json()]
    assert "Rigveda" in titles
    lessons = client.get("/api/scriptures/rigveda/lessons", headers=headers)
    assert lessons.status_code == 200
    assert lessons.json()[0]["sanskrit"].startswith("सत्येनोत्तभिता")


def test_signup_requires_email_but_phone_login_remains_supported(client):
    start = client.post("/api/auth/register", json={"identifier": "9988776655"})
    assert start.status_code == 422
    assert client.post(
        "/api/auth/complete-signup",
        json={"identifier": "9988776655", "full_name": "Phone User", "password": "password1", "verification_token": "x" * 43},
    ).status_code == 422


def test_resending_verification_invalidates_old_link(client):
    from urllib.parse import parse_qs, urlparse

    created = client.post("/api/auth/register", json={"email": "resend-link@example.com"})
    old_token = parse_qs(urlparse(created.json()["demo_verification_url"]).query)["signup_token"][0]
    resent = client.post("/api/auth/resend-verification", json={"email": "resend-link@example.com"})
    assert resent.status_code == 200
    new_token = parse_qs(urlparse(resent.json()["demo_verification_url"]).query)["signup_token"][0]
    assert old_token != new_token
    assert client.post("/api/auth/verify-email-link", json={"email": "resend-link@example.com", "verification_token": old_token}).status_code == 400
    assert client.post("/api/auth/verify-email-link", json={"email": "resend-link@example.com", "verification_token": new_token}).status_code == 200


def test_password_reset(client):
    register_verified_tokens(client, "reset2@example.com")
    forgot = client.post("/api/auth/forgot-password", json={"email": "reset2@example.com"})
    assert forgot.status_code == 200
    reset_otp = forgot.json().get("demo_otp")
    if reset_otp:
        changed = client.post(
            "/api/auth/reset-password",
            json={"email": "reset2@example.com", "otp": reset_otp, "new_password": "password2"},
        )
        assert changed.status_code == 200
        assert client.post("/api/auth/login", json={"email": "reset2@example.com", "password": "password2"}).status_code == 200


def test_seed_does_not_overwrite_guru_text(db):
    lesson = db.scalar(select(Lesson).where(Lesson.slug == "rigveda-01"))
    original = lesson.sanskrit_text
    lesson.sanskrit_text = "CHANGED"
    lesson.content_fingerprint = fingerprint("CHANGED", lesson.meaning)
    db.commit()
    seed_guru_lessons(db)
    db.refresh(lesson)
    assert lesson.sanskrit_text == "CHANGED"
    lesson.sanskrit_text = original
    lesson.content_fingerprint = fingerprint(original, lesson.meaning)
    db.commit()
