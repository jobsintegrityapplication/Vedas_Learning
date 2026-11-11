import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import Scripture, User, UserRole
from app.services.accounts import unique_username
from app.services.content_cms import import_rigveda_lessons

log = logging.getLogger(__name__)

CATALOG = [
    ("rigveda", "Rigveda", "Guru-approved lessons are added only from provided source material.", 1),
    ("yajurveda", "Yajurveda", "Lessons will appear when Guru-approved content is published.", 2),
    ("samaveda", "Samaveda", "Lessons will appear when Guru-approved content is published.", 3),
    ("atharvaveda", "Atharvaveda", "Lessons will appear when Guru-approved content is published.", 4),
    ("ramayana", "Ramayana", "Lessons will appear when Guru-approved content is published.", 5),
    ("mahabharata", "Mahabharata", "Lessons will appear when Guru-approved content is published.", 6),
    ("bhagavad-gita", "Bhagavad Gita", "Lessons will appear when Guru-approved content is published.", 7),
]


def seed_scriptures(db: Session) -> None:
    for slug, title, description, order in CATALOG:
        existing = db.scalar(select(Scripture).where(Scripture.slug == slug))
        if existing:
            continue
        db.add(Scripture(slug=slug, title=title, description=description, sort_order=order, is_published=True))
    db.flush()


def seed_guru_lessons(db: Session) -> None:
    path = Path(get_settings().content_path)
    if not path.is_file():
        log.warning("Guru content file not found at %s; skipping lesson seed", path)
        return
    import_rigveda_lessons(db, path)


def seed_admin(db: Session) -> None:
    settings = get_settings()
    email = settings.admin_email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        existing.role = UserRole.admin
        existing.is_verified = True
        existing.signup_completed = True
        existing.is_active = True
        if not existing.username:
            parts = settings.admin_name.split(None, 1)
            existing.username = unique_username(db, parts[0], parts[1] if len(parts) > 1 else "admin", email)
        if not verify_password(settings.admin_password, existing.password_hash):
            existing.password_hash = hash_password(settings.admin_password)
        return
    parts = settings.admin_name.split(None, 1)
    db.add(
        User(
            name=settings.admin_name,
            username=unique_username(db, parts[0], parts[1] if len(parts) > 1 else "admin", email),
            email=email,
            password_hash=hash_password(settings.admin_password),
            role=UserRole.admin,
            is_verified=True,
            signup_completed=True,
            is_active=True,
        )
    )
    log.info("Created admin user %s", email)


def seed_all(db: Session) -> None:
    seed_scriptures(db)
    seed_guru_lessons(db)
    seed_admin(db)
    db.commit()
