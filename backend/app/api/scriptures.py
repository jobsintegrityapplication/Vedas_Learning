from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import Chapter, Lesson, Scripture, User

router = APIRouter(prefix="/api/scriptures", tags=["scriptures"])


@router.get("")
def list_scriptures(_: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    lesson_count = (
        select(Lesson.scripture_id, func.count(Lesson.id).label("n"))
        .where(Lesson.is_published.is_(True))
        .group_by(Lesson.scripture_id)
        .subquery()
    )
    rows = db.execute(
        select(Scripture, func.coalesce(lesson_count.c.n, 0))
        .outerjoin(lesson_count, lesson_count.c.scripture_id == Scripture.id)
        .where(Scripture.is_published.is_(True))
        .order_by(Scripture.sort_order)
    ).all()
    return [
        {
            "id": str(scripture.id),
            "slug": scripture.slug,
            "title": scripture.title,
            "description": scripture.description,
            "lesson_count": int(count),
        }
        for scripture, count in rows
    ]


@router.get("/{slug}/chapters")
def list_chapters(slug: str, _: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    scripture = db.scalar(select(Scripture).where(Scripture.slug == slug, Scripture.is_published.is_(True)))
    if scripture is None:
        raise HTTPException(404, "Scripture not found")
    rows = db.scalars(
        select(Chapter)
        .where(Chapter.scripture_id == scripture.id, Chapter.is_published.is_(True))
        .order_by(Chapter.sort_order, Chapter.title)
    ).all()
    return [
        {
            "id": str(chapter.id),
            "scripture_id": str(chapter.scripture_id),
            "title": chapter.title,
            "sort_order": chapter.sort_order,
        }
        for chapter in rows
    ]
