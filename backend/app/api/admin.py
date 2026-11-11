from datetime import datetime, timezone
from collections import Counter
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_admin_user
from app.db.session import get_db
from app.models import (
    Chapter,
    GuruReferenceAudio,
    LearningEvent,
    Lesson,
    LessonAudit,
    LessonVersion,
    Progress,
    Profile,
    Recording,
    Scripture,
    User,
    UsageSession,
)
from app.schemas.content import ChapterIn, LessonIn, PublishIn, RestoreIn, ScriptureIn
from app.services.content_cms import (
    apply_fingerprint,
    import_rigveda_lessons,
    lesson_guru_state,
    next_version_number,
    publish_lesson,
    require_guru_confirmation,
    snapshot_lesson,
    unpublish_lesson,
    write_audit,
    write_version,
)
from app.services.content_integrity import guru_field_changes, shloka_number_from_reference
from app.services.storage import object_key, put_bytes
from app.services.uploads import read_audio_upload

router = APIRouter(prefix="/api/admin", tags=["admin"])


class WordAudioTimingIn(BaseModel):
    word_order: int = Field(ge=0)
    word: str = Field(min_length=1, max_length=80)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class WordAudioTimingsIn(BaseModel):
    words: list[WordAudioTimingIn]


def _lesson_word_tokens(text: str) -> list[str]:
    return [re.sub(r"[।॥,;:!?]+$", "", word) for word in text.split() if word]


@router.get("/customer-insights")
def customer_insights(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Admin-only aggregate learner metrics. No personally identifying rows are returned."""
    rows = db.execute(
        select(User.last_login_at, Profile.date_of_birth, Profile.gender, Profile.profession)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(User.role == "learner", User.signup_completed.is_(True))
    ).all()
    now = datetime.now(timezone.utc)
    age_bands = {"Under 18": 0, "18–24": 0, "25–34": 0, "35–44": 0, "45–54": 0, "55+": 0, "Not provided": 0}
    genders: Counter[str] = Counter()
    professions: Counter[str] = Counter()
    logged_in_ever = logged_in_7d = logged_in_30d = 0
    for last_login, date_of_birth, gender, profession in rows:
        if last_login:
            logged_in_ever += 1
            if last_login.tzinfo is None:
                last_login = last_login.replace(tzinfo=timezone.utc)
            days = (now - last_login).days
            logged_in_7d += days < 7
            logged_in_30d += days < 30
        try:
            dob = datetime.strptime(date_of_birth or "", "%Y-%m-%d").date()
            age = now.date().year - dob.year - ((now.date().month, now.date().day) < (dob.month, dob.day))
            band = "Under 18" if age < 18 else "18–24" if age <= 24 else "25–34" if age <= 34 else "35–44" if age <= 44 else "45–54" if age <= 54 else "55+"
            age_bands[band] += 1
        except (TypeError, ValueError):
            age_bands["Not provided"] += 1
        if gender:
            genders[gender] += 1
        if profession:
            professions[profession.strip()] += 1
    session_rows = db.scalars(
        select(UsageSession.active_seconds)
        .join(User, User.id == UsageSession.user_id)
        .where(User.role == "learner", User.signup_completed.is_(True))
    ).all()
    ended_session_rows = db.scalars(
        select(UsageSession.active_seconds)
        .join(User, User.id == UsageSession.user_id)
        .where(User.role == "learner", User.signup_completed.is_(True), UsageSession.ended_at.is_not(None))
    ).all()
    total_app_seconds = sum(session_rows)
    total_learning_seconds = db.scalar(
        select(func.sum(LearningEvent.duration_seconds))
        .join(User, User.id == LearningEvent.user_id)
        .where(User.role == "learner", User.signup_completed.is_(True), LearningEvent.event_type == "lesson_time")
    ) or 0
    course_rows = db.execute(
        select(Scripture.slug, Scripture.title, func.count(LearningEvent.id), func.avg(LearningEvent.duration_seconds))
        .join(LearningEvent, LearningEvent.scripture_id == Scripture.id)
        .join(User, User.id == LearningEvent.user_id)
        .where(User.role == "learner", User.signup_completed.is_(True), LearningEvent.event_type == "course_completed")
        .group_by(Scripture.slug, Scripture.title)
    ).all()
    event_rows = db.execute(
        select(LearningEvent.event_type, func.count(LearningEvent.id))
        .join(User, User.id == LearningEvent.user_id)
        .where(User.role == "learner", User.signup_completed.is_(True))
        .group_by(LearningEvent.event_type)
    ).all()
    lessons_completed = db.scalar(
        select(func.count(Progress.id))
        .join(User, User.id == Progress.user_id)
        .where(User.role == "learner", User.signup_completed.is_(True), Progress.completed_at.is_not(None))
    ) or 0
    return {
        "registered_customers": len(rows),
        "logged_in_ever": logged_in_ever,
        "logged_in_last_7_days": logged_in_7d,
        "logged_in_last_30_days": logged_in_30d,
        "age_bands": age_bands,
        "genders": dict(genders.most_common()),
        "professions": dict(professions.most_common(10)),
        "total_app_time_seconds": int(total_app_seconds),
        "average_session_seconds": int(sum(ended_session_rows) / len(ended_session_rows)) if ended_session_rows else 0,
        "total_learning_time_seconds": int(total_learning_seconds),
        "lessons_completed": int(lessons_completed),
        "course_completions": sum(int(row[2]) for row in course_rows),
        "average_course_period_seconds": int(sum((row[3] or 0) * row[2] for row in course_rows) / sum(row[2] for row in course_rows)) if course_rows else 0,
        "course_completions_by_scripture": [
            {"slug": slug, "title": title, "completions": int(count), "average_period_seconds": int(avg_seconds or 0)}
            for slug, title, count, avg_seconds in course_rows
        ],
        "activity_events": {event_type: int(count) for event_type, count in event_rows},
    }


@router.get("/customer-activity")
def customer_activity(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    user_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
):
    query = (
        select(LearningEvent, User, Scripture, Lesson)
        .join(User, User.id == LearningEvent.user_id)
        .outerjoin(Scripture, Scripture.id == LearningEvent.scripture_id)
        .outerjoin(Lesson, Lesson.id == LearningEvent.lesson_id)
        .where(User.role == "learner", User.signup_completed.is_(True))
    )
    if user_id is not None:
        query = query.where(LearningEvent.user_id == user_id)
    query = query.order_by(LearningEvent.occurred_at.desc()).limit(limit)
    rows = db.execute(query).all()
    return [
        {
            "user_id": str(user.id),
            "customer": (user.profile.name if user.profile and user.profile.name else user.name or user.username or "Learner"),
            "username": user.username,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "duration_seconds": event.duration_seconds,
            "scripture": scripture.title if scripture else None,
            "lesson": lesson.title if lesson else None,
        }
        for event, user, scripture, lesson in rows
    ]


@router.get("/customers/{user_id}/activity")
def customer_activity_detail(user_id: UUID, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    customer = db.get(User, user_id)
    if customer is None or customer.role != "learner" or not customer.signup_completed:
        raise HTTPException(404, "Customer not found")
    sessions = db.scalars(
        select(UsageSession).where(UsageSession.user_id == user_id).order_by(UsageSession.started_at.desc()).limit(100)
    ).all()
    events = db.execute(
        select(LearningEvent, Scripture, Lesson)
        .outerjoin(Scripture, Scripture.id == LearningEvent.scripture_id)
        .outerjoin(Lesson, Lesson.id == LearningEvent.lesson_id)
        .where(LearningEvent.user_id == user_id)
        .order_by(LearningEvent.occurred_at.desc())
        .limit(250)
    ).all()
    learning_seconds = db.scalar(
        select(func.sum(LearningEvent.duration_seconds)).where(LearningEvent.user_id == user_id, LearningEvent.event_type == "lesson_time")
    ) or 0
    completed_lessons = db.scalar(select(func.count(Progress.id)).where(Progress.user_id == user_id, Progress.completed_at.is_not(None))) or 0
    course_completions = db.scalar(select(func.count(LearningEvent.id)).where(LearningEvent.user_id == user_id, LearningEvent.event_type == "course_completed")) or 0
    course_rows = db.execute(
        select(Scripture, Lesson, Progress)
        .join(Lesson, Lesson.scripture_id == Scripture.id)
        .outerjoin(Progress, (Progress.lesson_id == Lesson.id) & (Progress.user_id == user_id))
        .where(Scripture.is_published.is_(True), Lesson.is_published.is_(True))
    ).all()
    courses: dict[str, dict] = {}
    for scripture, lesson, progress in course_rows:
        course = courses.setdefault(scripture.slug, {"slug": scripture.slug, "title": scripture.title, "lessons_total": 0, "lessons_completed": 0, "first_started_at": None, "completed_at": None})
        course["lessons_total"] += 1
        if progress and progress.completed_at:
            course["lessons_completed"] += 1
            course["completed_at"] = max(course["completed_at"] or progress.completed_at, progress.completed_at)
        if progress and progress.first_started_at:
            course["first_started_at"] = min(course["first_started_at"] or progress.first_started_at, progress.first_started_at)
    for course in courses.values():
        course["is_completed"] = course["lessons_total"] > 0 and course["lessons_completed"] == course["lessons_total"]
        for key in ("first_started_at", "completed_at"):
            if course[key]:
                course[key] = course[key].isoformat()
    total_app_seconds = db.scalar(select(func.sum(UsageSession.active_seconds)).where(UsageSession.user_id == user_id)) or 0
    return {
        "user_id": str(customer.id),
        "customer": customer.profile.name if customer.profile and customer.profile.name else customer.name or customer.username or "Learner",
        "username": customer.username,
        "last_login_at": customer.last_login_at.isoformat() if customer.last_login_at else None,
        "total_app_time_seconds": int(total_app_seconds),
        "total_learning_time_seconds": int(learning_seconds),
        "lessons_completed": int(completed_lessons),
        "course_completions": int(course_completions),
        "courses": list(courses.values()),
        "sessions": [
            {"started_at": item.started_at.isoformat(), "ended_at": item.ended_at.isoformat() if item.ended_at else None, "active_seconds": item.active_seconds}
            for item in sessions
        ],
        "activity": [
            {"event_type": event.event_type, "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None, "duration_seconds": event.duration_seconds, "scripture": scripture.title if scripture else None, "lesson": lesson.title if lesson else None}
            for event, scripture, lesson in events
        ],
    }


def _lesson_out(lesson: Lesson) -> dict:
    return {
        "id": str(lesson.id),
        "slug": lesson.slug,
        "scripture_id": str(lesson.scripture_id),
        "chapter_id": str(lesson.chapter_id) if lesson.chapter_id else None,
        "title": lesson.title,
        "shloka_number": lesson.shloka_number,
        "canonical_reference": lesson.canonical_reference,
        "sanskrit_text": lesson.sanskrit_text,
        "word_audio_timings": lesson.word_audio_timings,
        "transliteration": lesson.transliteration,
        "meaning": lesson.meaning,
        "translation": lesson.translation,
        "translations": lesson.translations,
        "daily_application": lesson.daily_application,
        "word_meanings": lesson.word_meanings,
        "has_reference_audio": bool(lesson.reference_audio_key),
        "reference_audio": {
            "content_type": lesson.reference_audio_content_type,
            "byte_size": lesson.reference_audio_byte_size,
            "filename": lesson.reference_audio_filename,
            "storage_key": lesson.reference_audio_key,
        }
        if lesson.reference_audio_key
        else None,
        "source": lesson.source,
        "sort_order": lesson.sort_order,
        "is_published": lesson.is_published,
        "version_number": lesson.version_number,
        "published_at": lesson.published_at.isoformat() if lesson.published_at else None,
        "published_by_id": str(lesson.published_by_id) if lesson.published_by_id else None,
    }


@router.get("/dashboard")
def dashboard(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "scriptures": db.scalar(select(func.count(Scripture.id))) or 0,
        "chapters": db.scalar(select(func.count(Chapter.id))) or 0,
        "lessons": db.scalar(select(func.count(Lesson.id))) or 0,
        "published_lessons": db.scalar(select(func.count(Lesson.id)).where(Lesson.is_published.is_(True))) or 0,
        "recordings": db.scalar(select(func.count(Recording.id))) or 0,
        "practice_rows": db.scalar(select(func.count(Progress.id))) or 0,
    }


@router.get("/scriptures")
def admin_scriptures(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Scripture).order_by(Scripture.sort_order)).all()
    return [
        {
            "id": str(s.id),
            "slug": s.slug,
            "title": s.title,
            "description": s.description,
            "sort_order": s.sort_order,
            "is_published": s.is_published,
        }
        for s in rows
    ]


@router.post("/scriptures")
def create_scripture(body: ScriptureIn, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.scalar(select(Scripture).where(Scripture.slug == body.slug)):
        raise HTTPException(409, "Slug already exists")
    item = Scripture(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": str(item.id)}


@router.put("/scriptures/{scripture_id}")
def update_scripture(scripture_id: UUID, body: ScriptureIn, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    item = db.get(Scripture, scripture_id)
    if item is None:
        raise HTTPException(404, "Scripture not found")
    clash = db.scalar(select(Scripture).where(Scripture.slug == body.slug, Scripture.id != scripture_id))
    if clash:
        raise HTTPException(409, "Slug already exists")
    item.slug = body.slug
    item.title = body.title
    item.description = body.description
    item.sort_order = body.sort_order
    item.is_published = body.is_published
    db.commit()
    return {"updated": True}


@router.get("/chapters")
def admin_chapters(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Chapter).order_by(Chapter.sort_order, Chapter.title)).all()
    return [
        {
            "id": str(row.id),
            "scripture_id": str(row.scripture_id),
            "title": row.title,
            "sort_order": row.sort_order,
            "is_published": row.is_published,
        }
        for row in rows
    ]


@router.post("/chapters")
def create_chapter(body: ChapterIn, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.get(Scripture, body.scripture_id) is None:
        raise HTTPException(404, "Scripture not found")
    item = Chapter(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": str(item.id)}


@router.put("/chapters/{chapter_id}")
def update_chapter(chapter_id: UUID, body: ChapterIn, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    item = db.get(Chapter, chapter_id)
    if item is None:
        raise HTTPException(404, "Chapter not found")
    if db.get(Scripture, body.scripture_id) is None:
        raise HTTPException(404, "Scripture not found")
    item.scripture_id = body.scripture_id
    item.title = body.title
    item.sort_order = body.sort_order
    item.is_published = body.is_published
    db.commit()
    return {"updated": True}


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: UUID, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    item = db.get(Chapter, chapter_id)
    if item is None:
        raise HTTPException(404, "Chapter not found")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.get("/lessons")
def admin_lessons(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Lesson).order_by(Lesson.sort_order)).all()
    return [_lesson_out(lesson) for lesson in rows]


@router.get("/lessons/{lesson_id}")
def admin_lesson(lesson_id: UUID, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    return _lesson_out(lesson)


@router.put("/lessons/{lesson_id}/word-audio-timings")
def save_word_audio_timings(
    lesson_id: UUID,
    body: WordAudioTimingsIn,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    expected = _lesson_word_tokens(lesson.sanskrit_text)
    received = body.words
    if len(received) != len(expected):
        raise HTTPException(422, f"Expected timings for {len(expected)} Sanskrit words")
    previous_end = 0
    saved = []
    for index, (item, expected_word) in enumerate(zip(received, expected)):
        if item.word_order != index or item.word != expected_word:
            raise HTTPException(422, f"Word {index + 1} must match the published lesson text: {expected_word}")
        if item.end_ms <= item.start_ms or item.start_ms < previous_end:
            raise HTTPException(422, f"Word {index + 1} has invalid or overlapping audio boundaries")
        saved.append(item.model_dump())
        previous_end = item.end_ms
    lesson.word_audio_timings = saved
    write_audit(db, lesson, admin.id, "word_audio_timing_update", note=f"Saved {len(saved)} Guru word audio ranges")
    db.commit()
    return {"saved": True, "lesson_id": str(lesson.id), "word_count": len(saved)}


@router.post("/lessons")
def create_lesson(body: LessonIn, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.scalar(select(Lesson).where(Lesson.slug == body.slug)):
        raise HTTPException(409, "Lesson slug exists")
    if db.get(Scripture, body.scripture_id) is None:
        raise HTTPException(404, "Scripture not found")
    if body.chapter_id and db.get(Chapter, body.chapter_id) is None:
        raise HTTPException(404, "Chapter not found")
    item = Lesson(
        slug=body.slug,
        scripture_id=body.scripture_id,
        chapter_id=body.chapter_id,
        title=body.title,
        shloka_number=body.shloka_number or shloka_number_from_reference(body.canonical_reference),
        canonical_reference=body.canonical_reference,
        sanskrit_text=body.sanskrit_text,
        transliteration=body.transliteration,
        meaning=body.meaning,
        translation=body.translation,
        translations=body.translations,
        daily_application=body.daily_application,
        word_meanings=body.word_meanings,
        source="guru_provided",
        sort_order=body.sort_order,
        is_published=False,
        version_number=1,
    )
    apply_fingerprint(item)
    db.add(item)
    db.flush()
    write_version(db, item, admin.id, note=body.edit_note or "Created unpublished Guru content")
    write_audit(db, item, admin.id, "create", note=body.edit_note)
    db.commit()
    db.refresh(item)
    return {"id": str(item.id), "is_published": False, "version_number": item.version_number}


@router.put("/lessons/{lesson_id}")
def update_lesson(lesson_id: UUID, body: LessonIn, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    incoming = {
        "sanskrit_text": body.sanskrit_text,
        "meaning": body.meaning,
        "canonical_reference": body.canonical_reference,
        "transliteration": body.transliteration,
        "translation": body.translation,
        "translations": body.translations,
        "word_meanings": body.word_meanings,
    }
    changed = guru_field_changes(lesson_guru_state(lesson), incoming)
    require_guru_confirmation(changed, body.confirm_guru_edit, body.edit_note)
    previous = snapshot_lesson(lesson)
    lesson.slug = body.slug
    lesson.scripture_id = body.scripture_id
    lesson.chapter_id = body.chapter_id
    lesson.title = body.title
    lesson.shloka_number = body.shloka_number or shloka_number_from_reference(body.canonical_reference)
    lesson.canonical_reference = body.canonical_reference
    lesson.sanskrit_text = body.sanskrit_text
    lesson.transliteration = body.transliteration
    lesson.meaning = body.meaning
    lesson.translation = body.translation
    lesson.translations = body.translations
    lesson.daily_application = body.daily_application
    lesson.word_meanings = body.word_meanings
    lesson.sort_order = body.sort_order
    apply_fingerprint(lesson)
    if changed:
        lesson.version_number = next_version_number(db, lesson.id)
        write_version(db, lesson, admin.id, note=body.edit_note)
    write_audit(
        db,
        lesson,
        admin.id,
        "guru_text_edit" if changed else "update",
        note=body.edit_note,
        previous=previous,
    )
    db.commit()
    return {"updated": True, "version_number": lesson.version_number, "guru_fields_changed": changed}


@router.post("/lessons/{lesson_id}/publish")
def publish(lesson_id: UUID, body: PublishIn, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    publish_lesson(db, lesson, admin, body.note)
    db.commit()
    return {"published": True, "version_number": lesson.version_number}


@router.post("/lessons/{lesson_id}/unpublish")
def unpublish(lesson_id: UUID, body: PublishIn, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    unpublish_lesson(db, lesson, admin, body.note)
    db.commit()
    return {"published": False, "version_number": lesson.version_number}


@router.get("/lessons/{lesson_id}/versions")
def list_versions(lesson_id: UUID, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.get(Lesson, lesson_id) is None:
        raise HTTPException(404, "Lesson not found")
    rows = db.scalars(
        select(LessonVersion).where(LessonVersion.lesson_id == lesson_id).order_by(LessonVersion.version_number)
    ).all()
    return [
        {
            "id": str(row.id),
            "version_number": row.version_number,
            "title": row.title,
            "shloka_number": row.shloka_number,
            "canonical_reference": row.canonical_reference,
            "sanskrit_text": row.sanskrit_text,
            "transliteration": row.transliteration,
            "meaning": row.meaning,
            "translation": row.translation,
            "translations": row.translations,
            "word_meanings": row.word_meanings,
            "daily_application": row.daily_application,
            "is_published": row.is_published,
            "note": row.note,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/lessons/{lesson_id}/versions/{version_number}/restore")
def restore_version(
    lesson_id: UUID,
    version_number: int,
    body: RestoreIn,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    row = db.scalar(
        select(LessonVersion).where(
            LessonVersion.lesson_id == lesson_id,
            LessonVersion.version_number == version_number,
        )
    )
    if row is None:
        raise HTTPException(404, "Version not found")
    incoming = {
        "sanskrit_text": row.sanskrit_text,
        "meaning": row.meaning,
        "canonical_reference": row.canonical_reference,
        "transliteration": row.transliteration,
        "translation": row.translation,
        "translations": row.translations,
        "word_meanings": row.word_meanings,
    }
    changed = guru_field_changes(lesson_guru_state(lesson), incoming)
    require_guru_confirmation(changed, body.confirm_guru_edit, body.edit_note)
    previous = snapshot_lesson(lesson)
    lesson.title = row.title
    lesson.shloka_number = row.shloka_number
    lesson.canonical_reference = row.canonical_reference
    lesson.sanskrit_text = row.sanskrit_text
    lesson.transliteration = row.transliteration
    lesson.meaning = row.meaning
    lesson.translation = row.translation
    lesson.translations = row.translations
    lesson.word_meanings = row.word_meanings
    lesson.daily_application = row.daily_application
    apply_fingerprint(lesson)
    if changed:
        lesson.version_number = next_version_number(db, lesson.id)
        write_version(db, lesson, admin.id, note=body.edit_note or f"Restored version {version_number}")
    write_audit(db, lesson, admin.id, "restore", note=body.edit_note, previous=previous)
    db.commit()
    return {"restored_from": version_number, "version_number": lesson.version_number}


@router.get("/lessons/{lesson_id}/audits")
def list_audits(lesson_id: UUID, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if db.get(Lesson, lesson_id) is None:
        raise HTTPException(404, "Lesson not found")
    rows = db.scalars(
        select(LessonAudit).where(LessonAudit.lesson_id == lesson_id).order_by(LessonAudit.created_at.desc())
    ).all()
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "note": row.note,
            "version_number": row.version_number,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "previous_sanskrit": row.previous_sanskrit,
            "previous_meaning": row.previous_meaning,
            "snapshot": row.snapshot,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/lessons/{lesson_id}/reference-audio")
async def upload_reference_audio(
    lesson_id: UUID,
    audio: UploadFile = File(...),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    data, content_type, filename, inspection = await read_audio_upload(audio)
    key = object_key("guru", str(lesson.id), filename)
    try:
        put_bytes(key, data, content_type)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    lesson.reference_audio_key = key
    lesson.reference_audio_content_type = content_type
    lesson.reference_audio_byte_size = len(data)
    lesson.reference_audio_filename = filename
    row = db.query(GuruReferenceAudio).filter(GuruReferenceAudio.lesson_id == lesson.id).one_or_none()
    if row is None:
        row = GuruReferenceAudio(lesson_id=lesson.id)
        db.add(row)
    row.storage_key = key
    row.content_type = content_type
    row.original_filename = filename
    row.byte_size = len(data)
    row.duration_ms = inspection.duration_ms
    row.sample_rate = inspection.sample_rate
    row.container = inspection.container
    row.uploaded_by_id = admin.id
    write_audit(db, lesson, admin.id, "reference_audio_upload", note=key)
    db.commit()
    return {
        "saved": True,
        "storage_key": key,
        "byte_size": len(data),
        "content_type": content_type,
        "filename": filename,
        "namespace": "guru",
        "duration_ms": inspection.duration_ms,
        "sample_rate": inspection.sample_rate,
        "container": inspection.container,
        "version_number": lesson.version_number,
    }


@router.post("/content/import-rigveda")
def import_rigveda(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    from pathlib import Path

    path = Path(get_settings().content_path)
    if not path.is_file():
        raise HTTPException(404, "Guru source file not found")
    result = import_rigveda_lessons(db, path, actor_id=admin.id)
    db.commit()
    return result


@router.get("/recordings")
def admin_recordings(_: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Recording).where(Recording.kind == "learner").order_by(Recording.created_at.desc()).limit(200)
    ).all()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "lesson_id": str(row.lesson_id),
            "line_index": row.line_index,
            "kind": row.kind,
            "byte_size": row.byte_size,
            "content_type": row.content_type,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
