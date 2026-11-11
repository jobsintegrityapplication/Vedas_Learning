import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_otp, verify_otp
from app.models import EmailOtp, OtpPurpose, User
from app.services.email import send_email


def issue_otp(db: Session, user: User, purpose: OtpPurpose) -> str:
    settings = get_settings()
    existing = db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id, EmailOtp.purpose == purpose))
    if existing:
        db.delete(existing)
        db.flush()
    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = EmailOtp(
        user_id=user.id,
        purpose=purpose,
        code_hash=hash_otp(code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.otp_ttl_seconds),
    )
    db.add(otp)
    minutes = max(1, settings.otp_ttl_seconds // 60)
    if purpose == OtpPurpose.verify:
        subject = "Verify your Vedas Learning email"
        greeting = user.name.strip() or "there"
        intro = f"Namaste {greeting},\n\nUse this one-time code to verify your email address:"
    else:
        greeting = user.name.strip() or "there"
        subject = "Reset your Vedas Learning password"
        intro = f"Namaste {greeting},\n\nUse this one-time code to reset your password:"
    body = (
        f"{intro}\n\n{code}\n\n"
        f"This code expires in {minutes} minutes. If you did not request it, ignore this email."
    )
    html = (
        f"<p>Namaste {greeting},</p>"
        f"<p>Your Vedas Learning one-time code is:</p>"
        f"<p style=\"font-size:28px;letter-spacing:6px;font-weight:bold\">{code}</p>"
        f"<p>This code expires in {minutes} minutes. If you did not request it, ignore this email.</p>"
    )
    send_email(user.email, subject, body, html_body=html)
    return code


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def consume_otp(db: Session, user: User, purpose: OtpPurpose, code: str) -> None:
    from fastapi import HTTPException

    settings = get_settings()
    otp = db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id, EmailOtp.purpose == purpose))
    if otp is None:
        raise HTTPException(400, "Invalid email or OTP")
    if otp.consumed_at is not None:
        raise HTTPException(400, "OTP already used")
    if datetime.now(timezone.utc) > _as_utc(otp.expires_at):
        raise HTTPException(400, "OTP expired")
    if otp.attempts >= settings.otp_max_attempts:
        raise HTTPException(429, "Too many OTP attempts")
    otp.attempts += 1
    if not verify_otp(code, otp.code_hash):
        db.flush()
        raise HTTPException(400, "Invalid email or OTP")
    otp.consumed_at = datetime.now(timezone.utc)
