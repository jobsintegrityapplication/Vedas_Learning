from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72


def _utf8_password(password: str) -> bytes:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Password exceeds bcrypt 72-byte limit")
    return raw


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_utf8_password(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_utf8_password(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


@lru_cache
def dummy_password_hash() -> str:
    return hash_password("not-a-real-account")


def hash_otp(otp: str) -> str:
    return hash_password(otp)


def verify_otp(otp: str, otp_hash: str) -> bool:
    return verify_password(otp, otp_hash)


def create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    minutes = get_settings().access_token_expire_minutes
    return create_token(str(user_id), "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: UUID, jti: UUID) -> str:
    days = get_settings().refresh_token_expire_days
    return create_token(str(user_id), "refresh", timedelta(days=days), extra={"jti": str(jti)})


def decode_token_payload(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    if not payload.get("sub"):
        raise jwt.InvalidTokenError("Missing subject")
    return payload


def decode_token(token: str, expected_type: str) -> str:
    return decode_token_payload(token, expected_type)["sub"]
