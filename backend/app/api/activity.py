from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import LearningEvent, Lesson, LessonLineProgress, Progress, Scripture, UsageSession, User
from app.services.lesson_unlock import line_has_accepted_match

router = APIRouter(prefix="/api/activity", tags=["activity"])


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _advance(session: UsageSession, now: datetime, finish: bool = False) -> None:
    # Count only time covered by a recent foreground heartbeat; cap each gap to resist inflated totals.
    elapsed = max(0, min(int((now - _utc(session.last_activity_at)).total_seconds()), 45))
    session.active_seconds += elapsed
    session.last_activity_at = now
    if finish:
        session.ended_at = now


@router.post("/sessions")
def start_usage_session(user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    open_sessions = db.scalars(select(UsageSession).where(UsageSession.user_id == user.id, UsageSession.ended_at.is_(None))).all()
    for old in open_sessions:
        if (now - _utc(old.last_activity_at)).total_seconds() > 300:
            old.ended_at = old.last_activity_at
    session = UsageSession(user_id=user.id, started_at=now, last_activity_at=now, active_seconds=0)
    db.add(session)
    db.add(LearningEvent(user_id=user.id, event_type="app_session_started", occurred_at=now))
    db.commit()
    db.refresh(session)
    return {"session_id": str(session.id), "started_at": session.started_at.isoformat()}


def _owned_session(session_id: UUID, user: User, db: Session) -> UsageSession:
    session = db.get(UsageSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(404, "Usage session not found")
    if session.ended_at is not None:
        raise HTTPException(409, "Usage session is already closed")
    return session


@router.post("/sessions/{session_id}/heartbeat")
def heartbeat_usage_session(session_id: UUID, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    session = _owned_session(session_id, user, db)
    _advance(session, datetime.now(timezone.utc))
    db.commit()
    return {"active_seconds": session.active_seconds}


@router.post("/sessions/{session_id}/end")
def end_usage_session(session_id: UUID, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    session = _owned_session(session_id, user, db)
    _advance(session, datetime.now(timezone.utc), finish=True)
    db.add(LearningEvent(user_id=user.id, event_type="app_session_ended", occurred_at=session.ended_at))
    db.commit()
    return {"active_seconds": session.active_seconds, "ended_at": session.ended_at.isoformat()}


class LearningEventIn(BaseModel):
    event_type: Literal[
        "scripture_opened", "lesson_opened", "lesson_time", "lesson_completed",
        "reference_audio_played", "recording_started", "learner_audio_played",
    ]
    scripture_slug: str | None = Field(default=None, max_length=100)
    lesson_slug: str | None = Field(default=None, max_length=160)
    duration_seconds: int = Field(default=0, ge=0, le=60)


@router.post("")
def record_learning_event(body: LearningEventIn, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    scripture = None
    lesson = None
    if body.event_type == "scripture_opened":
        if not body.scripture_slug:
            raise HTTPException(422, "scripture_slug is required")
        scripture = db.scalar(select(Scripture).where(Scripture.slug == body.scripture_slug, Scripture.is_published.is_(True)))
        if scripture is None:
            raise HTTPException(404, "Scripture not found")
    else:
        if not body.lesson_slug:
            raise HTTPException(422, "lesson_slug is required")
        lesson = db.scalar(select(Lesson).where(Lesson.slug == body.lesson_slug, Lesson.is_published.is_(True)))
        if lesson is None:
            raise HTTPException(404, "Lesson not found")
        scripture = db.get(Scripture, lesson.scripture_id)
        if body.event_type == "lesson_completed":
            lines = [line for line in lesson.sanskrit_text.splitlines() if line.strip()]
            completed_lines = set(db.scalars(select(LessonLineProgress.line_index).where(
                LessonLineProgress.user_id == user.id,
                LessonLineProgress.lesson_id == lesson.id,
            )).all())
            all_lines_passed = bool(lines) and all(
                index in completed_lines and line_has_accepted_match(
                    db, user_id=user.id, lesson_id=lesson.id, line_index=index
                )
                for index in range(len(lines))
            )
            if not all_lines_passed:
                raise HTTPException(409, "Complete every line after achieving at least 90% word match with its Guru reference.")

    progress = None
    if lesson is not None:
        progress = db.scalar(select(Progress).where(Progress.user_id == user.id, Progress.lesson_id == lesson.id))
        if progress is None and body.event_type in {"lesson_opened", "lesson_completed"}:
            progress = Progress(user_id=user.id, lesson_id=lesson.id, attempts=0, first_started_at=now)
            db.add(progress)
        elif progress is not None and progress.first_started_at is None:
            progress.first_started_at = now

    course_completed = False
    event_duration = body.duration_seconds if body.event_type == "lesson_time" else 0
    if body.event_type == "lesson_completed" and progress is not None:
        if progress.completed_at is None:
            progress.completed_at = now
            total_lessons = db.scalar(select(func.count(Lesson.id)).where(Lesson.scripture_id == scripture.id, Lesson.is_published.is_(True))) or 0
            completed_lessons = db.scalar(
                select(func.count(Progress.id))
                .join(Lesson, Lesson.id == Progress.lesson_id)
                .where(Progress.user_id == user.id, Lesson.scripture_id == scripture.id, Lesson.is_published.is_(True), Progress.completed_at.is_not(None))
            ) or 0
            course_completed = total_lessons > 0 and completed_lessons >= total_lessons
            if course_completed:
                first_start = db.scalar(
                    select(func.min(Progress.first_started_at))
                    .join(Lesson, Lesson.id == Progress.lesson_id)
                    .where(Progress.user_id == user.id, Lesson.scripture_id == scripture.id, Lesson.is_published.is_(True))
                )
                start_at = _utc(first_start) if first_start else now
                db.add(LearningEvent(user_id=user.id, scripture_id=scripture.id, event_type="course_completed", duration_seconds=max(0, int((now - start_at).total_seconds())), occurred_at=now))

    db.add(LearningEvent(
        user_id=user.id,
        scripture_id=scripture.id if scripture else None,
        lesson_id=lesson.id if lesson else None,
        event_type=body.event_type,
        duration_seconds=event_duration,
        occurred_at=now,
    ))
    db.commit()
    return {"recorded": True, "lesson_completed": bool(progress and progress.completed_at), "course_completed": course_completed}
