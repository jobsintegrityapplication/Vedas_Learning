from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import Evaluation, LearningEvent, Lesson, Progress, Recording, User
from app.core.rate_limit import limiter
from app.services.pipeline import public_report
from app.services.engines.registry import engine_is_configured
from app.services.storage import object_key, put_bytes
from app.services.uploads import read_audio_upload
from app.workers.tasks import evaluate_recording

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


@router.post("/evaluate")
@limiter.limit("10/minute")
async def submit_recording(
    request: Request,
    lesson_id: str = Form(..., min_length=1, max_length=80),
    line_index: int = Form(default=0, ge=0, le=99),
    recitation_profile: str = Form(default="Kanchi"),
    mantra_reference: str | None = Form(default=None, max_length=32),
    audio: UploadFile = File(...),
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    if recitation_profile not in {"Kanchi", "Sringeri", "Common"}:
        raise HTTPException(422, "recitation_profile must be Kanchi, Sringeri, or Common")
    if mantra_reference and not re.fullmatch(r"RV\.\d{2}\.\d{3}\.\d{2,3}", mantra_reference):
        raise HTTPException(422, "mantra_reference must use RV.MM.SSS.VV form")
    lesson = _resolve_lesson(db, lesson_id)
    if lesson is None or not lesson.is_published:
        raise HTTPException(404, "Lesson not found")
    lines = [line.strip() for line in lesson.sanskrit_text.splitlines() if line.strip()]
    if not lines or line_index >= len(lines):
        raise HTTPException(422, "Line index is outside this lesson")
    data, content_type, filename, inspection = await read_audio_upload(audio)
    key = object_key("learner", f"{user.id}/{recitation_profile}", filename)
    try:
        put_bytes(key, data, content_type)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    recording = Recording(
        user_id=user.id,
        lesson_id=lesson.id,
        line_index=line_index,
        recitation_profile=recitation_profile,
        mantra_reference=mantra_reference,
        storage_key=key,
        content_type=content_type,
        original_filename=filename,
        kind="learner",
        byte_size=len(data),
        duration_ms=inspection.duration_ms,
        sample_rate=inspection.sample_rate,
        container=inspection.container,
    )
    db.add(recording)
    db.flush()
    evaluation = Evaluation(recording_id=recording.id, status="queued")
    db.add(evaluation)
    progress = db.scalar(select(Progress).where(Progress.user_id == user.id, Progress.lesson_id == lesson.id))
    if progress is None:
        progress = Progress(user_id=user.id, lesson_id=lesson.id, attempts=0)
        db.add(progress)
    progress.attempts += 1
    progress.last_recording_id = recording.id
    progress.last_practiced_at = datetime.now(timezone.utc)
    db.add(LearningEvent(user_id=user.id, scripture_id=lesson.scripture_id, lesson_id=lesson.id, event_type="recording_submitted", occurred_at=datetime.now(timezone.utc)))
    db.commit()
    settings = get_settings()
    if settings.audio_store == "memory" or not engine_is_configured():
        # With no ASR provider there is no long-running work to queue. Return
        # the honest unavailable result immediately instead of leaving the
        # learner to poll a Celery job that cannot produce a score.
        evaluate_recording(str(recording.id))
        queued = False
        db.refresh(evaluation)
    else:
        try:
            evaluate_recording.delay(str(recording.id))
            queued = True
        except Exception:
            evaluate_recording(str(recording.id))
            queued = False
            db.refresh(evaluation)
    return {
        "recording_saved": True,
        "recording_id": str(recording.id),
        "line_index": recording.line_index,
        "recitation_profile": recording.recitation_profile,
        "mantra_reference": recording.mantra_reference,
        "queued": queued,
        "byte_size": recording.byte_size,
        "content_type": recording.content_type,
        "engine_status": evaluation.report["engine_status"] if evaluation.report else (
            evaluation.engine_id if evaluation.status != "queued" else "pending"
        ),
        "evaluation_status": evaluation.status,
        "word_accuracy_status": evaluation.word_accuracy_status,
        "pronunciation_status": evaluation.pronunciation_status,
        "svara_status": evaluation.svara_status,
        "alignment": evaluation.alignment,
        "report": public_report(evaluation.report),
        "message": evaluation.message
        or "Recording received. Evaluation will report only capabilities that a validated engine can provide.",
    }


@router.get("/{recording_id}")
def get_recording(recording_id: UUID, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    recording = db.get(Recording, recording_id)
    if recording is None or recording.user_id != user.id:
        raise HTTPException(404, "Recording not found")
    evaluation = db.query(Evaluation).filter(Evaluation.recording_id == recording.id).one_or_none()
    return {
        "recording_id": str(recording.id),
        "lesson_id": str(recording.lesson_id),
        "line_index": recording.line_index,
        "kind": recording.kind,
        "byte_size": recording.byte_size,
        "content_type": recording.content_type,
        "original_filename": recording.original_filename,
        "duration_ms": recording.duration_ms,
        "sample_rate": recording.sample_rate,
        "container": recording.container,
        "created_at": recording.created_at.isoformat() if recording.created_at else None,
        "status": evaluation.status if evaluation else "unknown",
        "word_accuracy": (evaluation.report or {}).get("word_accuracy")
        if evaluation and evaluation.report
        else {"status": evaluation.word_accuracy_status if evaluation else "unavailable"},
        "pronunciation": (evaluation.report or {}).get("pronunciation")
        if evaluation and evaluation.report
        else {"status": evaluation.pronunciation_status if evaluation else "unavailable"},
        "svara": (evaluation.report or {}).get("svara")
        if evaluation and evaluation.report
        else {"status": evaluation.svara_status if evaluation else "unavailable"},
        "alignment": evaluation.alignment if evaluation else None,
        "report": public_report(evaluation.report) if evaluation else None,
        "message": evaluation.message if evaluation else "",
    }


@router.get("/history/list")
def recording_history(user: User = Depends(get_verified_user), db: Session = Depends(get_db), limit: int = 100):
    rows = db.scalars(
        select(Recording).where(Recording.user_id == user.id, Recording.kind == "learner")
        .order_by(Recording.created_at.desc()).limit(max(1, min(limit, 200)))
    ).all()
    return [
        {
            "recording_id": str(row.id),
            "lesson_id": str(row.lesson_id),
            "line_index": row.line_index,
            "recitation_profile": row.recitation_profile,
            "mantra_reference": row.mantra_reference,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "duration_ms": row.duration_ms,
            "evaluation_status": row.evaluation.status if row.evaluation else "unknown",
            "word_accuracy_status": row.evaluation.word_accuracy_status if row.evaluation else "unavailable",
            "pronunciation_status": row.evaluation.pronunciation_status if row.evaluation else "unavailable",
            "svara_status": row.evaluation.svara_status if row.evaluation else "unavailable",
        }
        for row in rows
    ]


def _resolve_lesson(db: Session, lesson_id: str) -> Lesson | None:
    lesson = db.scalar(select(Lesson).where(Lesson.slug == lesson_id))
    if lesson:
        return lesson
    try:
        return db.get(Lesson, UUID(lesson_id))
    except ValueError:
        return None
