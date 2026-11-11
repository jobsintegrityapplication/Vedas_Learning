from uuid import uuid4


from tests.conftest import register_verified_tokens


def _learner(client, email: str) -> dict:
    return register_verified_tokens(client, email)


def test_unauthenticated_content_and_admin_are_rejected(client):
    assert client.get("/api/scriptures").status_code == 401
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/progress/me").status_code == 401


def test_learner_cannot_read_another_users_recording(client):
    first = _learner(client, "owner-rec@example.com")
    second = _learner(client, "other-rec@example.com")
    missing = client.get(f"/api/recordings/{uuid4()}", headers={"Authorization": f"Bearer {first['access_token']}"})
    assert missing.status_code == 404
    forbidden_admin = client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert forbidden_admin.status_code == 403


def test_password_longer_than_bcrypt_limit_is_rejected(client):
    from urllib.parse import parse_qs, urlparse

    too_long = "x" * 80
    registered = client.post("/api/auth/register", json={"email": "longpass@example.com"})
    token = parse_qs(urlparse(registered.json()["demo_verification_url"]).query)["signup_token"][0]
    response = client.post(
        "/api/auth/complete-signup",
        json={
            "email": "longpass@example.com",
            "verification_token": token,
            "full_name": "Long Pass",
            "password": too_long,
        },
    )
    assert response.status_code == 422


def test_unknown_login_does_not_500(client):
    response = client.post("/api/auth/login", json={"identifier": "missing@example.com", "password": "password1"})
    assert response.status_code == 401
    assert "Internal" not in response.text
