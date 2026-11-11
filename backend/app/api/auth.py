from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.core.security import dummy_password_hash, hash_password, verify_password
from app.db.session import get_db
from app.models import LearningEvent, OtpPurpose, Profile, User
from app.schemas.auth import (
    CompleteSignupRequest,
    DirectRegisterRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyRequest,
    VerifyEmailLinkRequest,
)
from app.services.accounts import (
    find_login_user,
    find_user_by_identifier,
    normalize_phone,
    parse_identifier,
    unique_username,
)
from app.services.email_verification import issue_signup_link, validate_signup_link
from app.services.otp import consume_otp, issue_otp
from app.services.tokens import issue_token_pair, revoke_user_refresh_tokens, rotate_refresh_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _maybe_otp(payload: dict, code: str) -> dict:
    if get_settings().expose_dev_otp:
        payload["demo_otp"] = code
    return payload


def _send_otp(db: Session, user: User, purpose: OtpPurpose) -> str:
    try:
        return issue_otp(db, user, purpose)
    except OSError as exc:
        raise HTTPException(503, "Unable to send email. Please try again.") from exc


def _send_signup_link(db: Session, user: User) -> str:
    try:
        return issue_signup_link(db, user)
    except OSError as exc:
        raise HTTPException(503, "Unable to send email. Please try again.") from exc


@router.post("/register")
@limiter.limit("10/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    email, phone = parse_identifier(body.start_id())
    if email is None or phone is not None:
        raise HTTPException(422, "Create an account with your email address. You can add a phone number after verification.")
    existing = find_user_by_identifier(db, body.start_id())
    if existing is not None:
        if existing.signup_completed:
            raise HTTPException(409, "This email is already registered. Please log in.")
        user = existing
    else:
        user = User(name="", email=email, phone=None, is_verified=False, signup_completed=False)
        db.add(user)
        db.flush()
    link = _send_signup_link(db, user)
    db.commit()
    payload = {"message": "Check your email for a link to verify your address and set your password.", "email_sent": True}
    if get_settings().expose_dev_otp:
        payload["demo_verification_url"] = link
    return payload


@router.post("/register-direct")
@limiter.limit("10/minute")
def register_direct(
    request: Request,
    body: DirectRegisterRequest,
    db: Session = Depends(get_db),
):
    """Temporary direct signup: create a login without email verification."""
    email = str(body.email).strip().lower()
    phone = normalize_phone(body.phone)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.signup_completed:
        raise HTTPException(409, "This email is already registered. Please log in.")
    phone_owner = db.scalar(select(User).where(User.phone == phone))
    if phone_owner is not None and (user is None or phone_owner.id != user.id):
        raise HTTPException(409, "This mobile number is already registered.")

    display_name = email.partition("@")[0].replace(".", " ").strip()[:200]
    if user is None:
        user = User(email=email)
        db.add(user)
    user.name = display_name
    user.email = email
    user.phone = phone
    user.password_hash = hash_password(body.password)
    user.is_verified = True
    user.signup_completed = True
    if not user.username:
        user.username = unique_username(db, display_name, "", email)

    try:
        db.flush()
        profile = db.get(Profile, user.id)
        if profile is None:
            profile = Profile(user_id=user.id)
            db.add(profile)
        profile.name = display_name
        profile.email = email
        profile.phone = phone
        db.add(
            LearningEvent(
                user_id=user.id,
                scripture_id=None,
                lesson_id=None,
                event_type="signup_completed",
                occurred_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This email or mobile number is already registered.") from exc
    return {
        "created": True,
        "email": email,
        "phone": phone,
        "message": "Account created. Log in with your email or mobile number.",
    }


@router.post("/resend-verification")
@limiter.limit("5/minute")
def resend_verification(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    payload = {"message": "If the account needs verification, a new link was sent"}
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or (user.is_verified and user.signup_completed):
        return payload
    link = _send_signup_link(db, user)
    db.commit()
    if get_settings().expose_dev_otp:
        payload["demo_verification_url"] = link
    return payload


@router.post("/verify-email-link")
@limiter.limit("10/minute")
def verify_email_link(request: Request, body: VerifyEmailLinkRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or user.signup_completed:
        raise HTTPException(400, "This verification link is invalid or has already been used. Request a new link.")
    validate_signup_link(db, user, body.verification_token)
    db.commit()
    return {"verified": True, "email": user.email, "message": "Email verified. Set your password to finish creating your account."}


@router.post("/verify")
@limiter.limit("10/minute")
def verify(request: Request, body: VerifyRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise HTTPException(400, "Invalid email or OTP")
    if user.is_verified and user.signup_completed:
        return {"message": "Email already verified. Please log in.", "verified": True, "needs_profile": False}
    consume_otp(db, user, OtpPurpose.verify, body.otp.strip())
    user.is_verified = True
    db.commit()
    return {"message": "Email verified. Complete your profile to continue.", "verified": True, "needs_profile": True}


@router.post("/complete-signup", response_model=TokenResponse)
@limiter.limit("10/minute")
def complete_signup(request: Request, body: CompleteSignupRequest, db: Session = Depends(get_db)):
    user = find_user_by_identifier(db, body.start_id())
    if user is None:
        raise HTTPException(400, "Create an account and verify your email before setting a password.")
    if user.signup_completed:
        raise HTTPException(409, "Account already created. Please log in.")
    validate_signup_link(db, user, body.verification_token, consume=True)
    full_name = body.display_name()
    parts = full_name.split(None, 1)
    requested = (body.username or "").strip().lower()
    if requested:
        if db.scalar(select(User.id).where(User.username == requested, User.id != user.id)):
            raise HTTPException(409, "This username is already taken")
        user.username = requested
    else:
        user.username = unique_username(db, parts[0], parts[1] if len(parts) > 1 else "", body.start_id())
    if body.phone:
        phone = parse_identifier(body.phone)[1] or user.phone
        taken = db.scalar(select(User).where(User.phone == phone, User.id != user.id))
        if taken is not None:
            raise HTTPException(409, "This mobile number is already registered")
        user.phone = phone
    user.name = full_name
    user.password_hash = hash_password(body.password)
    user.signup_completed = True
    signed_in_at = datetime.now(timezone.utc)
    user.last_login_at = signed_in_at
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    profile.name = user.name
    profile.email = user.email or ""
    profile.phone = user.phone or ""
    tokens = issue_token_pair(db, user)
    tokens["username"] = user.username
    db.add(LearningEvent(user_id=user.id, scripture_id=None, lesson_id=None, event_type="signup_completed", occurred_at=signed_in_at))
    db.commit()
    return tokens


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = find_login_user(db, body.login_id())
    if user is not None and not user.is_verified:
        raise HTTPException(403, "Verify your email using the link we sent before logging in.")
    if user is not None and not user.signup_completed:
        raise HTTPException(403, "Open your email verification link and set your password before logging in.")
    password_ok = verify_password(body.password, user.password_hash if user else dummy_password_hash())
    if user is None or not password_ok:
        raise HTTPException(401, "Invalid email, mobile number, or password")
    if not user.signup_completed:
        raise HTTPException(403, "Complete registration before login")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    signed_in_at = datetime.now(timezone.utc)
    user.last_login_at = signed_in_at
    db.add(LearningEvent(user_id=user.id, scripture_id=None, lesson_id=None, event_type="login", occurred_at=signed_in_at))
    tokens = issue_token_pair(db, user)
    tokens["username"] = user.username
    db.commit()
    return tokens


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    payload = {"message": "If the account exists, a reset code was sent"}
    if user is None:
        return payload
    code = _send_otp(db, user, OtpPurpose.reset)
    db.commit()
    return _maybe_otp(payload, code)


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise HTTPException(400, "Invalid email or OTP")
    consume_otp(db, user, OtpPurpose.reset, body.otp.strip())
    user.password_hash = hash_password(body.new_password)
    revoke_user_refresh_tokens(db, user.id)
    db.add(LearningEvent(user_id=user.id, event_type="password_reset"))
    db.commit()
    return {"message": "Password updated"}


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    tokens = rotate_refresh_token(db, body.refresh_token)
    db.commit()
    return tokens


@router.post("/logout")
@limiter.limit("30/minute")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_user_refresh_tokens(db, user.id)
    db.add(LearningEvent(user_id=user.id, event_type="logout"))
    db.commit()
    return {"logged_out": True}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        user_id=str(user.id),
        name=user.name,
        username=user.username,
        email=user.email,
        phone=user.phone,
        role=user.role.value,
        verified=user.is_verified,
    )
