import hashlib
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_admin_user, get_verified_user
from app.db.session import get_db
from app.models import RecitationReferenceAudio, RecitationTextVariant, Recording, User
from app.services.storage import object_key, presigned_get, put_bytes
from app.services.uploads import read_audio_upload

router = APIRouter(prefix="/api/recitation", tags=["recitation audio"])
ADMIN_PROFILES = {"Kanchi", "Sringeri", "Common"}
REFERENCE_RE = re.compile(r"^RV\.\d{2}\.\d{3}\.\d{2,3}$")


class ProfileTextIn(BaseModel):
    profile: str
    mantra_reference: str
    samhita_form: str
    padapatha_form: str
    padapatha_tokens: list[dict] = Field(min_length=1)
    phonetic_metadata: dict = Field(default_factory=dict)
    source_provenance: dict
    rights_status: str = "unknown"


class ProfileTextReviewIn(BaseModel):
    validation_status: str
    rights_status: str


@router.post("/admin/profile-text")
def add_profile_text(body: ProfileTextIn, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if body.profile not in ADMIN_PROFILES or not REFERENCE_RE.fullmatch(body.mantra_reference):
        raise HTTPException(422, "Provide a supported profile and canonical mantra address")
    if body.rights_status not in {"unknown", "cleared", "link_only", "permission_required", "restricted", "public_domain"}:
        raise HTTPException(422, "Unsupported rights_status")
    provenance = body.source_provenance
    if not provenance.get("source_title") or not provenance.get("source_locator") or not re.fullmatch(r"[0-9a-fA-F]{64}", str(provenance.get("source_sha256", ""))):
        raise HTTPException(422, "Source provenance must include title, locator, and 64-character SHA-256")
    for index, token in enumerate(body.padapatha_tokens, 1):
        if token.get("word_order") != index or not token.get("original_form"):
            raise HTTPException(422, "Padapāṭha tokens need contiguous word_order and source original_form")
    existing = db.scalar(select(RecitationTextVariant.id).where(
        RecitationTextVariant.profile == body.profile,
        RecitationTextVariant.mantra_reference == body.mantra_reference,
    ))
    if existing:
        raise HTTPException(409, "A profile text record already exists for this mantra")
    row = RecitationTextVariant(
        profile=body.profile, mantra_reference=body.mantra_reference, samhita_form=body.samhita_form,
        padapatha_form=body.padapatha_form, padapatha_tokens=body.padapatha_tokens,
        phonetic_metadata=body.phonetic_metadata, source_provenance=body.source_provenance,
        rights_status=body.rights_status, validation_status="pending",
    )
    db.add(row)
    db.commit()
    return {"id": str(row.id), "profile": row.profile, "mantra_reference": row.mantra_reference,
            "rights_status": row.rights_status, "validation_status": row.validation_status, "usable_for_evaluation": False}


@router.post("/admin/profile-text/{text_id}/review")
def review_profile_text(text_id: UUID, body: ProfileTextReviewIn, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if body.validation_status not in {"pending", "validated", "rejected"}:
        raise HTTPException(422, "Unsupported validation_status")
    if body.rights_status not in {"unknown", "cleared", "link_only", "permission_required", "restricted", "public_domain"}:
        raise HTTPException(422, "Unsupported rights_status")
    row = db.get(RecitationTextVariant, text_id)
    if row is None:
        raise HTTPException(404, "Profile text record not found")
    row.validation_status, row.rights_status, row.reviewer = body.validation_status, body.rights_status, admin.email
    db.commit()
    return {"id": str(row.id), "profile": row.profile, "validation_status": row.validation_status,
            "rights_status": row.rights_status,
            "usable_for_evaluation": row.validation_status == "validated" and row.rights_status in {"cleared", "public_domain"}}


@router.post("/admin/reference-audio")
async def upload_profile_reference(
    profile: str = Form(...), mantra_reference: str = Form(...), asset_kind: str = Form(...),
    source_title: str = Form(..., min_length=1, max_length=300),
    speaker_attribution: str = Form(..., min_length=1, max_length=300),
    source_attribution: str = Form(..., min_length=1, max_length=500),
    rights_status: str = Form(default="unknown"), rights_notes: str = Form(default=""),
    source_url: str | None = Form(default=None), word_order: int | None = Form(default=None, ge=1),
    start_ms: int | None = Form(default=None, ge=0), end_ms: int | None = Form(default=None, gt=0),
    audio: UploadFile = File(...), admin: User = Depends(get_admin_user), db: Session = Depends(get_db),
):
    if profile not in ADMIN_PROFILES or not REFERENCE_RE.fullmatch(mantra_reference):
        raise HTTPException(422, "Provide a Kanchi, Sringeri, or Common profile and a canonical RV.MM.SSS.VV reference")
    if asset_kind not in {"full_mantra", "word"}:
        raise HTTPException(422, "asset_kind must be full_mantra or word")
    if rights_status not in {"unknown", "cleared", "link_only", "permission_required", "restricted", "public_domain"}:
        raise HTTPException(422, "Unsupported rights_status")
    if asset_kind == "word" and (word_order is None or start_ms is None or end_ms is None or end_ms <= start_ms):
        raise HTTPException(422, "Word clips require word_order and valid start_ms/end_ms timestamps")
    if asset_kind == "full_mantra" and word_order is not None:
        raise HTTPException(422, "Full-mantra audio cannot have a word_order")
    duplicate = db.scalar(select(RecitationReferenceAudio.id).where(
        RecitationReferenceAudio.profile == profile,
        RecitationReferenceAudio.mantra_reference == mantra_reference,
        RecitationReferenceAudio.asset_kind == asset_kind,
        RecitationReferenceAudio.word_order.is_(None) if word_order is None else RecitationReferenceAudio.word_order == word_order,
    ))
    if duplicate:
        raise HTTPException(409, "An asset already exists for this profile, mantra, kind, and word order")
    data, content_type, filename, inspection = await read_audio_upload(audio)
    key = object_key("guru", f"{profile}/{mantra_reference}", filename)
    try:
        put_bytes(key, data, content_type)
    except RuntimeError as exc:
        raise HTTPException(503, "Audio storage is unavailable") from exc
    row = RecitationReferenceAudio(
        profile=profile, mantra_reference=mantra_reference, asset_kind=asset_kind, word_order=word_order,
        start_ms=start_ms, end_ms=end_ms, storage_key=key, source_url=source_url, source_title=source_title,
        speaker_attribution=speaker_attribution, source_attribution=source_attribution,
        rights_status=rights_status, rights_notes=rights_notes, validation_status="pending",
        validation_notes="", content_type=content_type, original_filename=filename, byte_size=len(data),
        duration_ms=inspection.duration_ms, sample_rate=inspection.sample_rate, container=inspection.container,
        sha256=hashlib.sha256(data).hexdigest(), uploaded_by_id=admin.id,
    )
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "An asset already exists for this profile, mantra, kind, and word order")
    return {"id": str(row.id), "profile": profile, "mantra_reference": mantra_reference,
            "asset_kind": asset_kind, "word_order": word_order, "rights_status": rights_status,
            "validation_status": row.validation_status, "sha256": row.sha256, "available": False}


@router.post("/admin/reference-audio/{asset_id}/review")
def review_profile_reference(asset_id: UUID, validation_status: str = Form(...), rights_status: str = Form(...),
                             validation_notes: str = Form(default=""), rights_notes: str = Form(default=""),
                             _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if validation_status not in {"pending", "validated", "rejected"}:
        raise HTTPException(422, "validation_status must be pending, validated, or rejected")
    if rights_status not in {"unknown", "cleared", "link_only", "permission_required", "restricted", "public_domain"}:
        raise HTTPException(422, "Unsupported rights_status")
    row = db.get(RecitationReferenceAudio, asset_id)
    if row is None:
        raise HTTPException(404, "Audio asset not found")
    row.validation_status, row.validation_notes = validation_status, validation_notes
    row.rights_status, row.rights_notes = rights_status, rights_notes
    db.commit()
    return {"id": str(row.id), "validation_status": row.validation_status, "rights_status": row.rights_status,
            "available": row.validation_status == "validated" and row.rights_status in {"cleared", "public_domain"}}


@router.get("/{mantra_reference}/audio")
def get_profile_audio(mantra_reference: str, profile: str, _: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in ADMIN_PROFILES or not REFERENCE_RE.fullmatch(mantra_reference):
        raise HTTPException(422, "Provide a supported profile and canonical mantra reference")
    rows = db.scalars(select(RecitationReferenceAudio).where(
        RecitationReferenceAudio.profile == profile,
        RecitationReferenceAudio.mantra_reference == mantra_reference,
    ).order_by(RecitationReferenceAudio.word_order)).all()
    def serialize(row):
        available = row.validation_status == "validated" and row.rights_status in {"cleared", "public_domain"}
        audio_url = presigned_get(row.storage_key) if available else None
        return {"id": str(row.id), "asset_kind": row.asset_kind, "word_order": row.word_order,
                "start_ms": row.start_ms, "end_ms": row.end_ms,
                "audio_url": audio_url,
                "available": bool(audio_url), "source_url": row.source_url,
                "source_title": row.source_title, "speaker_attribution": row.speaker_attribution,
                "source_attribution": row.source_attribution, "rights_status": row.rights_status,
                "validation_status": row.validation_status, "sha256": row.sha256}
    full = next((serialize(row) for row in rows if row.asset_kind == "full_mantra"), None)
    words = [serialize(row) for row in rows if row.asset_kind == "word"]
    return {"profile": profile, "mantra_reference": mantra_reference,
            "full_mantra": full or {"available": False, "audio_url": None, "validation_status": "not_uploaded"},
            "word_audio": words, "word_audio_available": bool(words) and all(x["available"] for x in words)}


@router.get("/learner-recordings")
def learner_recordings(profile: str, mantra_reference: str | None = None,
                       user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    if profile not in ADMIN_PROFILES:
        raise HTTPException(422, "profile must be Kanchi, Sringeri, or Common")
    query = select(Recording).where(Recording.user_id == user.id, Recording.recitation_profile == profile)
    if mantra_reference:
        query = query.where(Recording.mantra_reference == mantra_reference)
    rows = db.scalars(query.order_by(Recording.created_at.desc()).limit(200)).all()
    return [{"recording_id": str(row.id), "profile": row.recitation_profile, "mantra_reference": row.mantra_reference,
             "line_index": row.line_index, "created_at": row.created_at.isoformat() if row.created_at else None,
             "duration_ms": row.duration_ms} for row in rows]
