import re

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import LearningEvent, Lesson, Progress, ProgressiveMantraAttempt, ProgressiveMantraProgress, Recording, Scripture, UsageSession, User

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/me")
def my_progress(user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Progress, Lesson).join(Lesson, Lesson.id == Progress.lesson_id).where(Progress.user_id == user.id)
    ).all()
    history = [
        {
            "lesson_id": str(lesson.id),
            "slug": lesson.slug,
            "title": lesson.title,
            "reference": lesson.canonical_reference,
            "attempts": progress.attempts,
            "last_practiced_at": progress.last_practiced_at.isoformat() if progress.last_practiced_at else None,
            "first_started_at": progress.first_started_at.isoformat() if progress.first_started_at else None,
            "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
        }
        for progress, lesson in rows
    ]
    study_time_rows = db.execute(
        select(LearningEvent.lesson_id, func.sum(LearningEvent.duration_seconds))
        .where(LearningEvent.user_id == user.id, LearningEvent.event_type == "lesson_time")
        .group_by(LearningEvent.lesson_id)
    ).all()
    study_seconds_by_lesson = {str(lesson_id): int(seconds or 0) for lesson_id, seconds in study_time_rows}
    for item in history:
        item["time_spent_seconds"] = study_seconds_by_lesson.get(item["lesson_id"], 0)
    total_lessons = db.scalar(select(func.count(Lesson.id)).where(Lesson.is_published.is_(True))) or 0
    attempted = sum(1 for progress, _ in rows if progress.attempts > 0)
    recordings = db.scalar(select(func.count(Recording.id)).where(Recording.user_id == user.id)) or 0
    by_scripture_rows = db.execute(
        select(Scripture.slug, Scripture.title, func.count(Progress.id))
        .join(Lesson, Lesson.scripture_id == Scripture.id)
        .join(Progress, Progress.lesson_id == Lesson.id)
        .where(Progress.user_id == user.id, Progress.attempts > 0)
        .group_by(Scripture.slug, Scripture.title)
    ).all()
    lesson_rows = db.execute(
        select(Lesson, Scripture)
        .join(Scripture, Scripture.id == Lesson.scripture_id)
        .where(Lesson.is_published.is_(True), Scripture.is_published.is_(True))
    ).all()
    progress_by_lesson = {str(progress.lesson_id): progress for progress, _ in rows}
    courses: dict[str, dict] = {}
    for lesson, scripture in lesson_rows:
        course = courses.setdefault(scripture.slug, {"slug": scripture.slug, "title": scripture.title, "lessons_total": 0, "lessons_completed": 0, "started_at": None, "completed_at": None})
        course["lessons_total"] += 1
        item = progress_by_lesson.get(str(lesson.id))
        if item and item.completed_at:
            course["lessons_completed"] += 1
            course["completed_at"] = max(course["completed_at"] or item.completed_at, item.completed_at)
        if item and item.first_started_at:
            course["started_at"] = min(course["started_at"] or item.first_started_at, item.first_started_at)
    for course in courses.values():
        course["is_completed"] = course["lessons_total"] > 0 and course["lessons_completed"] == course["lessons_total"]
        if course["started_at"]:
            course["started_at"] = course["started_at"].isoformat()
        if course["completed_at"]:
            course["completed_at"] = course["completed_at"].isoformat()
    app_seconds = db.scalar(select(func.sum(UsageSession.active_seconds)).where(UsageSession.user_id == user.id)) or 0
    learning_seconds = db.scalar(select(func.sum(LearningEvent.duration_seconds)).where(LearningEvent.user_id == user.id, LearningEvent.event_type == "lesson_time")) or 0
    mantra_states = db.scalars(select(ProgressiveMantraProgress).where(ProgressiveMantraProgress.user_id == user.id)).all()
    attempt_counts = dict(db.execute(select(ProgressiveMantraAttempt.profile, func.count(ProgressiveMantraAttempt.id))
                                     .where(ProgressiveMantraAttempt.user_id == user.id)
                                     .group_by(ProgressiveMantraAttempt.profile)).all())
    profile_progress: dict[str, dict] = {}
    for state in mantra_states:
        item = profile_progress.setdefault(state.profile, {
            "profile": state.profile, "mantras_started": 0, "mantras_completed": 0,
            "bookmarks": 0, "words_completed": 0, "attempts": int(attempt_counts.get(state.profile, 0)),
            "by_mandala": {},
        })
        item["mantras_started"] += 1
        item["mantras_completed"] += int(state.completed_at is not None)
        item["bookmarks"] += int(state.bookmarked)
        item["words_completed"] += len(state.completed_word_orders or [])
        match = re.match(r"^RV\.(\d{2})\.", state.mantra_reference)
        if match:
            mandala = str(int(match.group(1)))
            mandala_row = item["by_mandala"].setdefault(mandala, {"mantras_started": 0, "mantras_completed": 0, "words_completed": 0})
            mandala_row["mantras_started"] += 1
            mandala_row["mantras_completed"] += int(state.completed_at is not None)
            mandala_row["words_completed"] += len(state.completed_word_orders or [])
    for profile, count in attempt_counts.items():
        profile_progress.setdefault(profile, {"profile": profile, "mantras_started": 0, "mantras_completed": 0,
                                                "bookmarks": 0, "words_completed": 0, "attempts": int(count), "by_mandala": {}})
    return {
        "lessons_published": total_lessons,
        "lessons_practiced": attempted,
        "recordings": recordings,
        "app_time_seconds": int(app_seconds),
        "learning_time_seconds": int(learning_seconds),
        "courses": list(courses.values()),
        "by_scripture": [
            {"slug": slug, "title": title, "lessons_practiced": int(count)}
            for slug, title, count in by_scripture_rows
        ],
        "history": history,
        "progressive_recitation": list(profile_progress.values()),
    }
