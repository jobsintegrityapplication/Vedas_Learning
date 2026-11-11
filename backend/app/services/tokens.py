import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_token_payload
from app.models import RefreshToken, User


def issue_token_pair(db: Session, user: User) -> dict:
    jti = uuid.uuid4()
    days = get_settings().refresh_token_expire_days
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    db.add(RefreshToken(id=jti, user_id=user.id, expires_at=expires))
    db.flush()
    return {
        "user_id": str(user.id),
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id, jti),
        "token_type": "bearer",
        "role": user.role.value,
        "verified": user.is_verified,
    }


def revoke_user_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


def rotate_refresh_token(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_token_payload(refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired refresh token")
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(401, "Invalid refresh token")
    row = db.get(RefreshToken, uuid.UUID(jti))
    now = datetime.now(timezone.utc)
    if row is None or row.revoked_at is not None:
        raise HTTPException(401, "Refresh token revoked")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        raise HTTPException(401, "Refresh token expired")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(401, "Account unavailable")
    row.revoked_at = now
    return issue_token_pair(db, user)
