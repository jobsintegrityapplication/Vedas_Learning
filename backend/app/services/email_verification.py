from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmailOtp, OtpPurpose, User
from app.services.email import send_email


def issue_signup_link(db: Session, user: User) -> str:
    settings = get_settings()
    existing = db.scalar(
        select(EmailOtp).where(EmailOtp.user_id == user.id, EmailOtp.purpose == OtpPurpose.verify)
    )
    if existing:
        db.delete(existing)
        db.flush()

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.add(EmailOtp(
        user_id=user.id,
        purpose=OtpPurpose.verify,
        code_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.email_verification_ttl_seconds),
    ))

    base = settings.frontend_base_url.rstrip("/")
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"signup_token": token, "email": user.email or ""})
    link = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), ""))
    safe_link = escape(link, quote=True)
    expiry_hours = max(1, (settings.email_verification_ttl_seconds + 3599) // 3600)
    body = (
        "Namaste,\n\nOpen this link to verify your email and set your Vedas Learning password:\n\n"
        f"{link}\n\nThis link expires in {expiry_hours} hours and can be used once. "
        "If you did not create this account, ignore this email."
    )
    html = (
        "<p>Namaste,</p><p>Verify your email and set your Vedas Learning password:</p>"
        f'<p><a href="{safe_link}">Verify email and set password</a></p>'
        f"<p>This link expires in {expiry_hours} hours and can be used once. If you did not create this account, ignore this email.</p>"
    )
    send_email(user.email or "", "Verify your Vedas Learning email", body, html_body=html)
    return link


def validate_signup_link(db: Session, user: User, token: str, *, consume: bool = False) -> None:
    row = db.scalar(
        select(EmailOtp).where(EmailOtp.user_id == user.id, EmailOtp.purpose == OtpPurpose.verify)
    )
    now = datetime.now(timezone.utc)
    if row is None or row.consumed_at is not None:
        raise HTTPException(400, "This verification link is invalid or has already been used. Request a new link.")
    expires_at = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if now > expires_at:
        raise HTTPException(400, "This verification link has expired. Request a new link.")
    actual_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not secrets.compare_digest(actual_hash, row.code_hash):
        raise HTTPException(400, "This verification link is invalid or has already been used. Request a new link.")
    user.is_verified = True
    if consume:
        row.consumed_at = now
