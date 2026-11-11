import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "unit-test-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["EVALUATION_ENGINE"] = "none"
os.environ["ALIGNMENT_ENGINE"] = "none"
os.environ["EVALUATION_TEST_MODE"] = "false"
os.environ["SANSKRIT_ASR_ENABLED"] = "false"
os.environ["PRONUNCIATION_EVALUATION_ENABLED"] = "false"
os.environ["WORD_MATCH_PASS_THRESHOLD_PERCENT"] = "90"
os.environ["SVARA_ENGINE"] = "none"
os.environ["AUDIO_STORE"] = "memory"
os.environ["EVALUATION_FIXTURE_DIR"] = str(Path(__file__).resolve().parent / "fixtures" / "audio")
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "AdminPass123"
os.environ["EXPOSE_DEV_OTP"] = "true"
os.environ["SMTP_HOST"] = "127.0.0.1"
os.environ["SMTP_PORT"] = "1"

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, get_engine, reset_engine
from app.models import *  # noqa: F401,F403
from app.services.seed import seed_all
from app.services.storage import reset_memory_store


def phone_for(email: str) -> str:
    import hashlib

    n = int(hashlib.md5(email.encode()).hexdigest()[:8], 16) % 10**9
    return f"9{n:09d}"


def register_verified_tokens(client, email: str, password: str = "password1", name: str = "Learner") -> dict:
    from urllib.parse import parse_qs, urlparse

    register = client.post("/api/auth/register", json={"email": email})
    assert register.status_code == 200, register.text
    link = register.json().get("demo_verification_url")
    assert link, "Test mode should return the generated signup link"
    query = parse_qs(urlparse(link).query)
    token = query["signup_token"][0]
    verified = client.post("/api/auth/verify-email-link", json={"email": email, "verification_token": token})
    assert verified.status_code == 200, verified.text
    completed = client.post(
        "/api/auth/complete-signup",
        json={"email": email, "verification_token": token, "full_name": name, "password": password, "phone": phone_for(email)},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json().get("access_token")
    return completed.json()


@pytest.fixture()
def db(tmp_path: Path) -> Session:
    os.environ["EVALUATION_ENGINE"] = "none"
    os.environ["ALIGNMENT_ENGINE"] = "none"
    os.environ["EVALUATION_TEST_MODE"] = "false"
    os.environ["SANSKRIT_ASR_ENABLED"] = "false"
    os.environ["WORD_MATCH_PASS_THRESHOLD_PERCENT"] = "90"
    os.environ["SVARA_ENGINE"] = "none"
    os.environ["AUDIO_STORE"] = "memory"
    get_settings.cache_clear()
    reset_engine()
    reset_memory_store()
    supplied = Path(__file__).resolve().parents[2] / "content" / "rigveda_lessons.json"
    if supplied.is_file():
        os.environ["CONTENT_PATH"] = str(supplied)
    else:
        content = [
            {
                "id": "rigveda-01",
                "veda": "Rigveda",
                "title": "Truth – Righteousness",
                "reference": "Rigveda 10.85.1",
                "sanskrit": "सत्येनोत्तभिता भूमिः सूर्येणोत्तभिता द्यौः ।\nऋतेनादित्यास्तिष्ठन्ति दिवि सोमो अधि श्रितः ॥",
                "meaning": "By Truth the Earth is upheld; by Truth the heavens are upheld. By Yagna, the Ādityas stand firm; Soma abides in the celestial realm.",
                "dailyApplication": "Truth, righteousness, and morality are the foundation of our lives as well.",
                "referenceAudioUrl": None,
            }
        ]
        content_file = tmp_path / "lessons.json"
        content_file.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        os.environ["CONTENT_PATH"] = str(content_file)
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = SessionLocal()
    seed_all(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        reset_engine()
        get_settings.cache_clear()


@pytest.fixture()
def client(db: Session) -> TestClient:
    from app.core.rate_limit import limiter
    from app.main import app
    from app.db.session import get_db

    limiter.enabled = False

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
