from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chapter, Lesson, LessonAudit, LessonVersion, Scripture, User
from app.services.content_integrity import (
    fingerprint,
    guru_field_changes,
    mandala_from_reference,
    shloka_number_from_reference,
)

log = logging.getLogger(__name__)

IMPORT_ACTIONS = {"import", "create"}


def lesson_guru_state(lesson: Lesson) -> dict:
    return {
        "sanskrit_text": lesson.sanskrit_text,
        "meaning": lesson.meaning,
        "canonical_reference": lesson.canonical_reference,
        "transliteration": lesson.transliteration or "",
        "translation": lesson.translation or "",
        "translations": lesson.translations,
        "word_meanings": lesson.word_meanings,
    }


def snapshot_lesson(lesson: Lesson) -> dict:
    return {
        **lesson_guru_state(lesson),
        "title": lesson.title,
        "shloka_number": lesson.shloka_number or "",
        "daily_application": lesson.daily_application or "",
        "content_fingerprint": lesson.content_fingerprint,
        "reference_audio_key": lesson.reference_audio_key,
        "is_published": lesson.is_published,
        "version_number": lesson.version_number,
    }


def write_audit(
    db: Session,
    lesson: Lesson,
    actor_id: UUID | None,
    action: str,
    note: str = "",
    previous: dict | None = None,
) -> LessonAudit:
    audit = LessonAudit(
        lesson_id=lesson.id,
        actor_id=actor_id,
        action=action,
        note=note,
        version_number=lesson.version_number,
        previous_sanskrit=(previous or {}).get("sanskrit_text"),
        previous_meaning=(previous or {}).get("meaning"),
        snapshot=snapshot_lesson(lesson),
    )
    db.add(audit)
    return audit


def write_version(db: Session, lesson: Lesson, actor_id: UUID | None, note: str = "") -> LessonVersion:
    snap = snapshot_lesson(lesson)
    row = LessonVersion(
        lesson_id=lesson.id,
        version_number=lesson.version_number,
        actor_id=actor_id,
        note=note,
        title=snap["title"],
        shloka_number=snap["shloka_number"],
        canonical_reference=snap["canonical_reference"],
        sanskrit_text=snap["sanskrit_text"],
        transliteration=snap["transliteration"],
        meaning=snap["meaning"],
        translation=snap["translation"],
        translations=snap["translations"],
        word_meanings=snap["word_meanings"],
        daily_application=snap["daily_application"],
        content_fingerprint=snap["content_fingerprint"],
        reference_audio_key=snap["reference_audio_key"],
        is_published=snap["is_published"],
    )
    db.add(row)
    return row


def require_guru_confirmation(changed: list[str], confirm: bool, note: str) -> None:
    if not changed:
        return
    if not confirm:
        raise HTTPException(
            409,
            "Guru-approved Sanskrit, meaning, transliteration, translation or reference would change. "
            "Resubmit with confirm_guru_edit=true and an edit note. The API never rewrites Guru text.",
        )
    if not note.strip():
        raise HTTPException(400, "An edit note is required when changing Guru-approved fields")


def next_version_number(db: Session, lesson_id: UUID) -> int:
    current = db.scalar(select(func.max(LessonVersion.version_number)).where(LessonVersion.lesson_id == lesson_id))
    return int(current or 0) + 1


def apply_fingerprint(lesson: Lesson) -> None:
    lesson.content_fingerprint = fingerprint(lesson.sanskrit_text, lesson.meaning)


def publish_lesson(db: Session, lesson: Lesson, admin: User, note: str = "") -> Lesson:
    if lesson.is_published:
        return lesson
    lesson.is_published = True
    lesson.published_at = datetime.now(timezone.utc)
    lesson.published_by_id = admin.id
    write_audit(db, lesson, admin.id, "publish", note or "Published by admin")
    return lesson


def unpublish_lesson(db: Session, lesson: Lesson, admin: User, note: str = "") -> Lesson:
    if not lesson.is_published:
        return lesson
    lesson.is_published = False
    write_audit(db, lesson, admin.id, "unpublish", note or "Unpublished by admin")
    return lesson


def ensure_chapter(db: Session, scripture: Scripture, title: str) -> Chapter:
    existing = db.scalar(
        select(Chapter).where(Chapter.scripture_id == scripture.id, Chapter.title == title)
    )
    if existing:
        return existing
    max_order = db.scalar(select(func.max(Chapter.sort_order)).where(Chapter.scripture_id == scripture.id)) or 0
    chapter = Chapter(
        scripture_id=scripture.id,
        title=title,
        sort_order=int(max_order) + 1,
        is_published=True,
    )
    db.add(chapter)
    db.flush()
    return chapter


def load_guru_source(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Guru content file must be a JSON array")
    return payload


def import_source_item(item: dict) -> dict:
    """Copy supplied Guru fields verbatim. Never invent transliteration or translations."""
    sanskrit = item["sanskrit"]
    meaning = item["meaning"]
    reference = item["reference"]
    return {
        "slug": item["id"],
        "title": item["title"],
        "canonical_reference": reference,
        "sanskrit_text": sanskrit,
        "meaning": meaning,
        "daily_application": item.get("dailyApplication") or "",
        "transliteration": item["transliteration"] if "transliteration" in item and item["transliteration"] is not None else "",
        "translation": item["translation"] if "translation" in item and item["translation"] is not None else "",
        "translations": item.get("translations"),
        "word_meanings": item.get("wordMeanings") or item.get("word_meanings"),
        "shloka_number": item.get("shlokaNumber") or shloka_number_from_reference(reference),
        "reference_audio_url": item.get("referenceAudioUrl"),
    }


def import_rigveda_lessons(db: Session, path: Path, actor_id: UUID | None = None) -> dict:
    payload = load_guru_source(path)
    scripture = db.scalar(select(Scripture).where(Scripture.slug == "rigveda"))
    if scripture is None:
        raise RuntimeError("Rigveda scripture row missing")
    inserted = 0
    skipped = 0
    refused = 0
    for index, item in enumerate(payload, start=1):
        copied = import_source_item(item)
        slug = copied["slug"]
        existing = db.scalar(select(Lesson).where(Lesson.slug == slug))
        if existing:
            if existing.sanskrit_text != copied["sanskrit_text"] or existing.meaning != copied["meaning"]:
                log.critical("Refusing to overwrite Guru lesson %s; database text differs from source file", slug)
                refused += 1
            else:
                skipped += 1
            continue
        chapter_title = mandala_from_reference(copied["canonical_reference"])
        chapter = ensure_chapter(db, scripture, chapter_title) if chapter_title else None
        lesson = Lesson(
            slug=slug,
            scripture_id=scripture.id,
            chapter_id=chapter.id if chapter else None,
            title=copied["title"],
            shloka_number=copied["shloka_number"],
            canonical_reference=copied["canonical_reference"],
            sanskrit_text=copied["sanskrit_text"],
            transliteration=copied["transliteration"],
            meaning=copied["meaning"],
            translation=copied["translation"],
            translations=copied["translations"],
            daily_application=copied["daily_application"],
            word_meanings=copied["word_meanings"],
            reference_audio_key=None,
            content_fingerprint=fingerprint(copied["sanskrit_text"], copied["meaning"]),
            source="guru_provided",
            sort_order=index,
            is_published=True,
            version_number=1,
            published_at=datetime.now(timezone.utc),
            published_by_id=actor_id,
        )
        db.add(lesson)
        db.flush()
        write_version(db, lesson, actor_id, note="Imported from Guru source file without wording changes")
        write_audit(db, lesson, actor_id, "import", note=str(path))
        inserted += 1
        log.info("Inserted Guru-provided lesson %s", slug)
    return {"inserted": inserted, "skipped_unchanged": skipped, "refused_overwrite": refused, "source": str(path)}
