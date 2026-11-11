import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_verified_user
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import (ProgressiveMantraAttempt, ProgressiveMantraProgress, RecitationReferenceAudio,
                        RecitationTextVariant, User)
from app.services.pipeline import public_report, run_evaluation_pipeline
from app.services.storage import get_bytes, object_key, presigned_get, put_bytes
from app.services.uploads import read_audio_upload

router = APIRouter(prefix="/api/recitation", tags=["progressive mantra learning"])
PROFILES = {"Kanchi", "Sringeri", "Common"}
REF_RE = re.compile(r"^RV\.(\d{2})\.(\d{3})\.(\d{2,3})$")
EXPECTED_SUKTAS = {1:191,2:43,3:62,4:58,5:87,6:75,7:104,8:103,9:114,10:191}
EXPECTED_MANTRAS = {1:2006,2:429,3:617,4:589,5:727,6:765,7:841,8:1716,9:1108,10:1754}


class ResumeIn(BaseModel):
    word_order: int = Field(ge=1)


class BookmarkIn(BaseModel):
    bookmarked: bool


def _tokens(variant: RecitationTextVariant) -> list[dict]:
    return sorted(variant.padapatha_tokens or [], key=lambda item: item.get("word_order", 0))


def _available_audio(db: Session, profile: str, ref: str, kind: str, word_order: int | None = None):
    row = db.scalar(select(RecitationReferenceAudio).where(
        RecitationReferenceAudio.profile == profile, RecitationReferenceAudio.mantra_reference == ref,
        RecitationReferenceAudio.asset_kind == kind,
        RecitationReferenceAudio.word_order.is_(None) if word_order is None else RecitationReferenceAudio.word_order == word_order,
        RecitationReferenceAudio.validation_status == "validated",
        RecitationReferenceAudio.rights_status.in_(["cleared", "public_domain"]),
    ))
    return row


def _state(db: Session, user_id, profile: str, ref: str) -> ProgressiveMantraProgress:
    row = db.scalar(select(ProgressiveMantraProgress).where(
        ProgressiveMantraProgress.user_id == user_id, ProgressiveMantraProgress.profile == profile,
        ProgressiveMantraProgress.mantra_reference == ref,
    ))
    if row is None:
        row = ProgressiveMantraProgress(user_id=user_id, profile=profile, mantra_reference=ref)
        db.add(row)
        db.flush()
    return row


def _profile_text(db: Session, profile: str, ref: str):
    return db.scalar(select(RecitationTextVariant).where(
        RecitationTextVariant.profile == profile, RecitationTextVariant.mantra_reference == ref,
        RecitationTextVariant.validation_status == "validated",
        RecitationTextVariant.rights_status.in_(["cleared", "public_domain"]),
    ))


@router.get("/library-index")
def library_index(profile: str, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in PROFILES:
        raise HTTPException(422, "profile must be Kanchi, Sringeri, or Common")
    reviewed = db.scalars(select(RecitationTextVariant).where(
        RecitationTextVariant.profile == profile,
        RecitationTextVariant.validation_status == "validated",
        RecitationTextVariant.rights_status.in_(["cleared", "public_domain"]),
    ).order_by(RecitationTextVariant.mantra_reference)).all()
    groups: dict[int, dict[int, list[str]]] = {m: {} for m in range(1, 11)}
    for row in reviewed:
        match = REF_RE.fullmatch(row.mantra_reference)
        if match:
            mandala, sukta = int(match.group(1)), int(match.group(2))
            groups.setdefault(mandala, {}).setdefault(sukta, []).append(row.mantra_reference)
    mandalas = []
    for m in range(1, 11):
        suktas = [{"sukta": s, "available_mantra_count": len(groups[m].get(s, [])),
                   "available_mantras": sorted(groups[m].get(s, [])),
                   "status": "available" if groups[m].get(s) else "awaiting_reviewed_corpus"}
                  for s in range(1, EXPECTED_SUKTAS[m] + 1)]
        mandalas.append({"mandala": m, "expected_sukta_count": EXPECTED_SUKTAS[m], "expected_mantra_count": EXPECTED_MANTRAS[m],
                         "available_sukta_count": sum(bool(x["available_mantras"]) for x in suktas),
                         "available_mantra_count": sum(x["available_mantra_count"] for x in suktas),
                         "suktas": suktas})
    return {"profile": profile, "mandalas": mandalas,
            "expected_total_suktas": 1028, "expected_total_mantras": 10552,
            "available_mantra_count": sum(m["available_mantra_count"] for m in mandalas),
            "status": "available" if reviewed else "awaiting_reviewed_corpus"}


@router.get("/learning-mantras")
def learning_mantras(profile: str, mandala: int | None = None, sukta: int | None = None, bookmarked: bool | None = None,
                     user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in PROFILES or (mandala is not None and not 1 <= mandala <= 10) or (sukta is not None and sukta < 1):
        raise HTTPException(422, "profile must be Kanchi, Sringeri, or Common; Mandala and Sūkta filters must be positive and valid")
    rows = db.scalars(select(RecitationTextVariant).where(
        RecitationTextVariant.profile == profile,
        RecitationTextVariant.validation_status == "validated",
        RecitationTextVariant.rights_status.in_(["cleared", "public_domain"]),
    ).order_by(RecitationTextVariant.mantra_reference)).all()
    result = []
    for row in rows:
        match = REF_RE.fullmatch(row.mantra_reference)
        if not match or (mandala is not None and int(match.group(1)) != mandala) or (sukta is not None and int(match.group(2)) != sukta):
            continue
        state = db.scalar(select(ProgressiveMantraProgress).where(
            ProgressiveMantraProgress.user_id == user.id, ProgressiveMantraProgress.profile == profile,
            ProgressiveMantraProgress.mantra_reference == row.mantra_reference,
        ))
        if bookmarked is not None and bool(state and state.bookmarked) != bookmarked:
            continue
        word_count = len(_tokens(row))
        result.append({"profile": profile, "mantra_reference": row.mantra_reference,
                       "mandala": int(match.group(1)), "sukta": int(match.group(2)), "mantra": int(match.group(3)),
                       "word_count": word_count, "current_word_order": state.current_word_order if state else 1,
                       "unlocked_word_order": state.unlocked_word_order if state else 1,
                       "completed_word_count": len(state.completed_word_orders or []) if state else 0,
                       "bookmarked": bool(state and state.bookmarked), "combined_passed": bool(state and state.combined_passed),
                       "completed": bool(state and state.completed_at),
                       "full_audio_available": _available_audio(db, profile, row.mantra_reference, "full_mantra") is not None})
    return {"profile": profile, "mandala": mandala, "count": len(result), "mantras": result,
            "unavailable_note": None if result else "No reviewed, rights-cleared Padapāṭha mantras are currently available for this profile and selection."}


@router.get("/{mantra_reference}/learning")
def mantra_learning(mantra_reference: str, profile: str, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in PROFILES or not REF_RE.fullmatch(mantra_reference):
        raise HTTPException(422, "Provide a supported profile and canonical mantra address")
    variant = _profile_text(db, profile, mantra_reference)
    if variant is None:
        return {"profile": profile, "mantra_reference": mantra_reference, "status": "unavailable",
                "reason": "No reviewed, rights-cleared profile-specific Padapāṭha is available.", "words": [],
                "full_audio_available": False, "evaluation_available": False}
    state = _state(db, user.id, profile, mantra_reference)
    tokens = _tokens(variant)
    words = []
    for token in tokens:
        order = token["word_order"]
        audio = _available_audio(db, profile, mantra_reference, "word", order)
        words.append({**token, "unlocked": order <= state.unlocked_word_order,
                      "completed": order in (state.completed_word_orders or []),
                      "audio_available": audio is not None,
                      "audio_url": presigned_get(audio.storage_key) if audio else None})
    full = _available_audio(db, profile, mantra_reference, "full_mantra")
    return {"profile": profile, "mantra_reference": mantra_reference, "status": "available",
            "samhita_form": variant.samhita_form, "padapatha_form": variant.padapatha_form,
            "words": words, "full_audio_available": full is not None,
            "full_audio_url": presigned_get(full.storage_key) if full else None,
            "evaluation_available": True, "current_word_order": state.current_word_order,
            "unlocked_word_order": state.unlocked_word_order,
            "completed_word_orders": state.completed_word_orders or [], "bookmarked": state.bookmarked,
            "combined_passed": state.combined_passed,
            "completed": state.completed_at is not None}


@router.post("/{mantra_reference}/resume")
def resume_mantra(mantra_reference: str, profile: str, body: ResumeIn,
                  user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    variant = _profile_text(db, profile, mantra_reference)
    if variant is None or profile not in PROFILES or not REF_RE.fullmatch(mantra_reference):
        raise HTTPException(404, "Reviewed mantra is unavailable for this profile")
    state = _state(db, user.id, profile, mantra_reference)
    if body.word_order > state.unlocked_word_order or body.word_order > len(_tokens(variant)):
        raise HTTPException(409, "Cannot resume at a locked word")
    state.current_word_order = body.word_order
    db.commit()
    return {"profile": profile, "mantra_reference": mantra_reference,
            "current_word_order": state.current_word_order, "unlocked_word_order": state.unlocked_word_order}


@router.put("/{mantra_reference}/bookmark")
def set_bookmark(mantra_reference: str, profile: str, body: BookmarkIn,
                 user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in PROFILES or _profile_text(db, profile, mantra_reference) is None:
        raise HTTPException(404, "Reviewed mantra is unavailable for this profile")
    state = _state(db, user.id, profile, mantra_reference)
    state.bookmarked = body.bookmarked
    db.commit()
    return {"profile": profile, "mantra_reference": mantra_reference, "bookmarked": state.bookmarked}


@router.post("/{mantra_reference}/attempt")
@limiter.limit("20/minute")
async def submit_attempt(mantra_reference: str, request: Request,
                         profile: str = Form(...), mode: str = Form(...), word_order: int = Form(default=0, ge=0),
                         audio: UploadFile = File(...), user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in PROFILES or mode not in {"word", "combined", "full_mantra"}:
        raise HTTPException(422, "Use a supported profile and mode word, combined, or full_mantra")
    variant = _profile_text(db, profile, mantra_reference)
    if variant is None:
        raise HTTPException(409, "Reviewed profile-specific mantra text is unavailable")
    tokens = _tokens(variant)
    state = _state(db, user.id, profile, mantra_reference)
    if mode == "word" and (word_order < 1 or word_order > state.unlocked_word_order or word_order > len(tokens)):
        raise HTTPException(409, "Only the currently unlocked word can be practiced")
    if mode == "combined" and (word_order < 2 or word_order > state.unlocked_word_order or any(i not in state.completed_word_orders for i in range(1, word_order + 1))):
        raise HTTPException(409, "Combined recitation requires the contiguous word sequence to be learned first")
    if mode == "full_mantra" and not state.combined_passed:
        raise HTTPException(409, "Pass the combined learned-words recitation before the full mantra")

    data, content_type, filename, inspection = await read_audio_upload(audio)
    attempt = ProgressiveMantraAttempt(user_id=user.id, profile=profile, mantra_reference=mantra_reference,
                                       mode=mode, word_order=word_order, storage_key="pending", content_type=content_type,
                                       byte_size=len(data), duration_ms=inspection.duration_ms)
    db.add(attempt)
    db.flush()
    key = object_key("learner", f"{user.id}/{profile}/{mantra_reference}/{attempt.id}", filename)
    put_bytes(key, data, content_type)
    attempt.storage_key = key

    start_idx, end_idx = (word_order - 1, word_order) if mode == "word" else (0, word_order if mode == "combined" else len(tokens))
    expected_rows = tokens[start_idx:end_idx]
    expected_tokens = [row.get("original_form", "") for row in expected_rows]
    asset = _available_audio(db, profile, mantra_reference, "word", word_order) if mode == "word" else _available_audio(db, profile, mantra_reference, "full_mantra")
    reference_bytes = reference_type = reference_name = None
    if asset:
        stored = get_bytes(asset.storage_key)
        if stored:
            reference_bytes, reference_type = stored
            reference_name = asset.original_filename
    report = run_evaluation_pipeline(
        learner_bytes=data, learner_filename=filename, learner_content_type=content_type, learner_storage_key=key,
        guru_text="", guru_bytes=reference_bytes, guru_filename=reference_name, guru_content_type=reference_type,
        guru_storage_key=asset.storage_key if asset and reference_bytes else None, lesson_slug=mantra_reference,
        recitation_profile=profile, mantra_reference=mantra_reference, reference_tokens=expected_tokens,
        reference_phonetic_metadata=variant.phonetic_metadata,
    )
    attempt.report = report
    attempt.evaluation_status = report["word_accuracy"]["status"]
    attempt.passed = report.get("accepted") is True
    next_unlocked = False
    if attempt.passed:
        if mode == "word":
            completed = set(state.completed_word_orders or [])
            completed.add(word_order)
            state.completed_word_orders = sorted(completed)
            state.current_word_order = min(word_order + 1, len(tokens))
            if word_order == state.unlocked_word_order and word_order < len(tokens):
                state.unlocked_word_order += 1
                next_unlocked = True
            if len(tokens) == 1:
                state.combined_passed = True
        elif mode == "combined" and word_order < len(tokens):
            state.unlocked_word_order = max(state.unlocked_word_order, word_order + 1)
            state.current_word_order = word_order + 1
            next_unlocked = True
        elif mode == "combined" and word_order == len(tokens):
            state.combined_passed = True
        elif mode == "full_mantra":
            state.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)
    return {"attempt_id": str(attempt.id), "profile": profile, "mantra_reference": mantra_reference,
            "mode": mode, "word_order": word_order, "passed": attempt.passed,
            "evaluation_status": attempt.evaluation_status, "next_word_unlocked": next_unlocked,
            "progress": {"current_word_order": state.current_word_order, "unlocked_word_order": state.unlocked_word_order,
                         "completed_word_orders": state.completed_word_orders or [], "completed": state.completed_at is not None},
            "final_report": public_report(report) if mode == "full_mantra" else None, "report": public_report(report)}


@router.get("/{mantra_reference}/attempts")
def attempt_history(mantra_reference: str, profile: str, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in PROFILES or not REF_RE.fullmatch(mantra_reference):
        raise HTTPException(422, "Provide a supported profile and canonical mantra address")
    rows = db.scalars(select(ProgressiveMantraAttempt).where(
        ProgressiveMantraAttempt.user_id == user.id, ProgressiveMantraAttempt.profile == profile,
        ProgressiveMantraAttempt.mantra_reference == mantra_reference,
    ).order_by(ProgressiveMantraAttempt.created_at.desc()).limit(200)).all()
    return [{"attempt_id": str(row.id), "profile": row.profile, "mode": row.mode, "word_order": row.word_order,
             "evaluation_status": row.evaluation_status, "passed": row.passed,
             "created_at": row.created_at.isoformat() if row.created_at else None, "report": public_report(row.report)} for row in rows]
