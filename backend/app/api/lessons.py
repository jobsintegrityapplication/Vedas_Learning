from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import Chapter, Lesson, LessonLineProgress, Progress, Scripture, User
from app.services.lesson_unlock import line_has_accepted_match
from app.services.storage import presigned_get

router = APIRouter(prefix="/api", tags=["lessons"])


class CompleteLineIn(BaseModel):
    line_index: int = Field(ge=0, le=99)


def _serialize(lesson: Lesson) -> dict:
    return {
        "id": str(lesson.id),
        "slug": lesson.slug,
        "title": lesson.title,
        "reference": lesson.canonical_reference,
        "shloka_number": lesson.shloka_number or None,
        "sanskrit": lesson.sanskrit_text,
        "lines": [line.strip() for line in lesson.sanskrit_text.splitlines() if line.strip()],
        "svara_status": "unavailable_not_in_source",
        "pronunciation_guidance_status": "guru_review_required",
        "transliteration": lesson.transliteration or None,
        "iast_lines": [line.strip() for line in (lesson.transliteration or "").splitlines() if line.strip()],
        "iast_status": "guru_review_required" if lesson.transliteration else "not_provided",
        "meaning": lesson.meaning,
        "translation": lesson.translation or None,
        "translations": lesson.translations,
        "version_number": lesson.version_number,
        "daily_application": lesson.daily_application or None,
        "word_meanings": lesson.word_meanings,
        "chapter_id": str(lesson.chapter_id) if lesson.chapter_id else None,
        "reference_audio_url": presigned_get(lesson.reference_audio_key) if lesson.reference_audio_key else None,
        "word_audio_timings": lesson.word_audio_timings,
        "has_reference_audio": bool(lesson.reference_audio_key),
        "reference_audio": {
            "content_type": lesson.reference_audio_content_type,
            "byte_size": lesson.reference_audio_byte_size,
            "filename": lesson.reference_audio_filename,
        } if lesson.reference_audio_key else None,
        "source": lesson.source,
    }


@router.get("/scriptures/{slug}/lessons")
def list_lessons(
    slug: str,
    chapter_id: UUID | None = Query(default=None),
    _: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    scripture = db.scalar(select(Scripture).where(Scripture.slug == slug, Scripture.is_published.is_(True)))
    if scripture is None:
        raise HTTPException(404, "Scripture not found")
    query = select(Lesson).where(Lesson.scripture_id == scripture.id, Lesson.is_published.is_(True))
    if chapter_id is not None:
        query = query.where(Lesson.chapter_id == chapter_id)
    lessons = db.scalars(query.order_by(Lesson.sort_order)).all()
    return [_serialize(lesson) for lesson in lessons]


@router.get("/chapters/{chapter_id}/lessons")
def list_chapter_lessons(chapter_id: UUID, _: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or not chapter.is_published:
        raise HTTPException(404, "Chapter not found")
    lessons = db.scalars(
        select(Lesson)
        .where(Lesson.chapter_id == chapter.id, Lesson.is_published.is_(True))
        .order_by(Lesson.sort_order)
    ).all()
    return [_serialize(lesson) for lesson in lessons]


@router.get("/lessons/{slug}")
def get_lesson(slug: str, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    lesson = db.scalar(select(Lesson).where(Lesson.slug == slug, Lesson.is_published.is_(True)))
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    payload = _serialize(lesson)
    progress = db.scalar(select(Progress).where(Progress.user_id == user.id, Progress.lesson_id == lesson.id))
    payload["completed_at"] = progress.completed_at.isoformat() if progress and progress.completed_at else None
    done = db.scalars(select(LessonLineProgress).where(
        LessonLineProgress.user_id == user.id, LessonLineProgress.lesson_id == lesson.id
    ).order_by(LessonLineProgress.line_index)).all()
    payload["completed_line_indices"] = [row.line_index for row in done]
    payload["line_completion_policy"] = "requires_90_percent_word_match_against_reviewed_Guru_reference"
    return payload


@router.post("/lessons/{slug}/lines/complete")
def complete_line(slug: str, body: CompleteLineIn, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    lesson = db.scalar(select(Lesson).where(Lesson.slug == slug, Lesson.is_published.is_(True)))
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    lines = [line for line in lesson.sanskrit_text.splitlines() if line.strip()]
    if body.line_index >= len(lines):
        raise HTTPException(422, "Line index is outside this lesson")
    if not line_has_accepted_match(db, user_id=user.id, lesson_id=lesson.id, line_index=body.line_index):
        raise HTTPException(409, "A passing Guru-reference word-match evaluation (at least 90%) is required before this line can be completed.")
    if body.line_index > 0:
        prior = db.scalar(select(LessonLineProgress).where(
            LessonLineProgress.user_id == user.id,
            LessonLineProgress.lesson_id == lesson.id,
            LessonLineProgress.line_index == body.line_index - 1,
        ))
        if prior is None:
            raise HTTPException(409, "Complete the previous line first")
    row = db.scalar(select(LessonLineProgress).where(
        LessonLineProgress.user_id == user.id,
        LessonLineProgress.lesson_id == lesson.id,
        LessonLineProgress.line_index == body.line_index,
    ))
    if row is None:
        row = LessonLineProgress(user_id=user.id, lesson_id=lesson.id, line_index=body.line_index)
        db.add(row)
        db.commit()
    return {"line_index": body.line_index, "completed": True, "policy": "90_percent_word_match"}
