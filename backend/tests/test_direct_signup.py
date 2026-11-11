from sqlalchemy import select

from app.core.security import verify_password
from app.models import Profile, User


def test_direct_signup_stores_password_and_allows_email_and_phone_login(client, db):
    response = client.post(
        "/api/auth/register-direct",
        json={
            "email": "direct-signup@example.com",
            "phone": "+1 (415) 555-0136",
            "password": "secure-pass-1",
            "confirm_password": "secure-pass-1",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["created"] is True
    assert "access_token" not in response.json()
    assert "verification" not in response.json()["message"].lower()

    user = db.scalar(select(User).where(User.email == "direct-signup@example.com"))
    assert user is not None
    assert user.phone == "14155550136"
    assert user.is_verified is True
    assert user.signup_completed is True
    assert user.password_hash != "secure-pass-1"
    assert verify_password("secure-pass-1", user.password_hash)

    profile = db.get(Profile, user.id)
    assert profile is not None
    assert profile.email == user.email
    assert profile.phone == user.phone

    by_email = client.post(
        "/api/auth/login",
        json={"identifier": "direct-signup@example.com", "password": "secure-pass-1"},
    )
    by_phone = client.post(
        "/api/auth/login",
        json={"identifier": "+1 (415) 555-0136", "password": "secure-pass-1"},
    )
    assert by_email.status_code == 200, by_email.text
    assert by_phone.status_code == 200, by_phone.text


def test_direct_signup_rejects_password_mismatch_and_duplicate_contacts(client):
    mismatch = client.post(
        "/api/auth/register-direct",
        json={
            "email": "mismatch@example.com",
            "phone": "9876543210",
            "password": "secure-pass-1",
            "confirm_password": "different-pass",
        },
    )
    assert mismatch.status_code == 422

    payload = {
        "email": "first-direct@example.com",
        "phone": "9876543210",
        "password": "secure-pass-1",
        "confirm_password": "secure-pass-1",
    }
    assert client.post("/api/auth/register-direct", json=payload).status_code == 200

    duplicate_email = client.post(
        "/api/auth/register-direct",
        json={**payload, "phone": "9876543211"},
    )
    duplicate_phone = client.post(
        "/api/auth/register-direct",
        json={**payload, "email": "second-direct@example.com"},
    )
    assert duplicate_email.status_code == 409
    assert duplicate_phone.status_code == 409
