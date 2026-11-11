import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def _token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_only.lower())[:24]


def unique_username(db: Session, first_name: str, last_name: str, fallback: str = "") -> str:
    first = _token(first_name) or "user"
    last = _token(last_name)
    base = f"{first}.{last}" if last else first
    if len(base) < 3:
        base = _token(fallback.split("@", 1)[0] if "@" in fallback else fallback) or "learner"
    candidate = base
    suffix = 1
    while db.scalar(select(User.id).where(User.username == candidate)):
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 10 or len(digits) > 15:
        raise HTTPException(400, "Enter a valid mobile number")
    return digits


def parse_identifier(identifier: str) -> tuple[str | None, str | None]:
    value = (identifier or "").strip()
    if not value:
        raise HTTPException(400, "Enter an email address or mobile number")
    if "@" in value:
        return value.lower(), None
    return None, normalize_phone(value)


def find_user_by_identifier(db: Session, identifier: str) -> User | None:
    email, phone = parse_identifier(identifier)
    if email:
        return db.scalar(select(User).where(User.email == email))
    return db.scalar(select(User).where(User.phone == phone))


def find_login_user(db: Session, identifier: str) -> User | None:
    value = identifier.strip()
    if not value:
        return None
    if "@" in value:
        return db.scalar(select(User).where(User.email == value.lower()))
    phone = re.sub(r"\D", "", value)
    if len(phone) < 10:
        return None
    return db.scalar(select(User).where(User.phone == phone))
