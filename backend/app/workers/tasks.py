import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.db.session import SessionLocal, get_engine
from app.models import Evaluation, Lesson, RecitationReferenceAudio, RecitationTextVariant, Recording
from app.services.pipeline import apply_report, profile_reference_unavailable, run_evaluation_pipeline
from app.services.engines.sanskrit_text import normalize_sanskrit_text
from app.services.storage import get_bytes
from app.workers.celery_app import celery

log = logging.getLogger(__name__)


def _development_candidate_tokens(lesson: Lesson | None) -> list[str]:
    """Return the full displayed shloka as candidate text for local diagnostics."""
    if lesson is None:
        return []
    return normalize_sanskrit_text(lesson.sanskrit_text or "").split()


def _development_diagnostic_enabled(settings) -> bool:
    return settings.evaluation_test_mode and settings.app_env.lower() in {"development", "dev", "local"}


def _development_guru_audio(settings, lesson: Lesson | None) -> tuple[bytes, str, str] | None:
    """Read the bundled Guru clip for local diagnostics only."""
    if lesson is None or not settings.development_guru_reference_dir:
        return None
    # Lesson slugs are application-owned IDs; constrain the path even in dev.
    if not lesson.slug.startswith("rigveda-") or not lesson.slug.removeprefix("rigveda-").isdigit():
        return None
    path = Path(settings.development_guru_reference_dir) / f"{lesson.slug}.ogg"
    try:
        if path.is_file():
            return path.read_bytes(), "audio/ogg", path.name
    except OSError:
        log.exception("Could not read local diagnostic Guru clip %s", path)
    return None


@celery.task(name="app.workers.tasks.evaluate_recording")
def evaluate_recording(recording_id: str) -> str:
    get_engine()
    db = SessionLocal()
    try:
        recording = db.get(Recording, UUID(recording_id))
        if recording is None:
            return "missing"
        lesson = db.get(Lesson, recording.lesson_id)
        evaluation = db.query(Evaluation).filter(Evaluation.recording_id == recording.id).one()
        learner = get_bytes(recording.storage_key)
        if learner is None:
            evaluation.status = "failed"
            evaluation.message = "Learner audio could not be read from storage."
            db.commit()
            return evaluation.status
        learner_bytes, learner_type = learner
        settings = get_settings()
        diagnostic_mode = _development_diagnostic_enabled(settings)
        text_variant = None
        if recording.mantra_reference and recording.recitation_profile in {"Kanchi", "Sringeri", "Common"}:
            text_variant = db.query(RecitationTextVariant).filter(
                RecitationTextVariant.profile == recording.recitation_profile,
                RecitationTextVariant.mantra_reference == recording.mantra_reference,
                RecitationTextVariant.validation_status == "validated",
                RecitationTextVariant.rights_status.in_(["cleared", "public_domain"]),
            ).one_or_none()
        reference_is_reviewed = text_variant is not None
        if text_variant is None and not diagnostic_mode:
            report = profile_reference_unavailable(
                recording.recitation_profile, recording.mantra_reference,
                "No reviewed, rights-cleared Padapāṭha text exists for this exact recitation profile and mantra. Evaluation was not run against another tradition or unverified lesson text.",
            )
            apply_report(evaluation, report)
            evaluation.completed_at = datetime.now(timezone.utc)
            db.commit()
            return evaluation.status

        if text_variant is None:
            reference_tokens = _development_candidate_tokens(lesson)
            if not reference_tokens:
                report = profile_reference_unavailable(
                    recording.recitation_profile, recording.mantra_reference,
                    "Development diagnostic mode could not find the displayed lesson line.",
                )
                apply_report(evaluation, report)
                evaluation.completed_at = datetime.now(timezone.utc)
                db.commit()
                return evaluation.status
            phonetic_metadata = {}
        else:
            token_rows = text_variant.padapatha_tokens if isinstance(text_variant.padapatha_tokens, list) else []
            token_rows = sorted(token_rows, key=lambda item: item.get("word_order", 0) if isinstance(item, dict) else 0)
            reference_tokens = [item.get("original_form", "") for item in token_rows if isinstance(item, dict) and item.get("original_form")]
            phonetic_metadata = text_variant.phonetic_metadata
            if not reference_tokens:
                report = profile_reference_unavailable(recording.recitation_profile, recording.mantra_reference,
                                                       "The approved profile text has no usable source word sequence.")
                apply_report(evaluation, report)
                evaluation.completed_at = datetime.now(timezone.utc)
                db.commit()
                return evaluation.status

        audio_row = db.query(RecitationReferenceAudio).filter(
            RecitationReferenceAudio.profile == recording.recitation_profile,
            RecitationReferenceAudio.mantra_reference == recording.mantra_reference,
            RecitationReferenceAudio.asset_kind == "full_mantra",
            RecitationReferenceAudio.validation_status == "validated",
            RecitationReferenceAudio.rights_status.in_(["cleared", "public_domain"]),
        ).one_or_none()
        guru_key = audio_row.storage_key if audio_row else (
            lesson.reference_audio_key if diagnostic_mode and lesson and lesson.reference_audio_key else None
        )
        guru_bytes = guru_type = guru_name = None
        if guru_key:
            stored = get_bytes(guru_key)
            if stored:
                guru_bytes, guru_type = stored
                guru_name = audio_row.original_filename if audio_row else "lesson-reference.ogg"
        if diagnostic_mode and guru_bytes is None:
            local_guru = _development_guru_audio(settings, lesson)
            if local_guru:
                guru_bytes, guru_type, guru_name = local_guru
                guru_key = f"guru/development-diagnostic/{guru_name}"
        report = run_evaluation_pipeline(
            learner_bytes=learner_bytes,
            learner_filename=recording.original_filename or "learner.wav",
            learner_content_type=learner_type or recording.content_type,
            learner_storage_key=recording.storage_key,
            guru_text="",
            guru_bytes=guru_bytes,
            guru_filename=guru_name,
            guru_content_type=guru_type,
            guru_storage_key=guru_key,
            lesson_slug=lesson.slug if lesson else "",
            recitation_profile=recording.recitation_profile,
            mantra_reference=recording.mantra_reference,
            reference_tokens=reference_tokens,
            reference_phonetic_metadata=phonetic_metadata,
            reference_is_reviewed=reference_is_reviewed,
        )
        apply_report(evaluation, report)
        evaluation.completed_at = datetime.now(timezone.utc)
        db.commit()
        return evaluation.status
    except Exception:
        log.exception("Evaluation task failed for %s", recording_id)
        db.rollback()
        try:
            evaluation = db.query(Evaluation).filter(Evaluation.recording_id == UUID(recording_id)).one_or_none()
            if evaluation is not None:
                evaluation.status = "failed"
                evaluation.message = "Evaluation failed. No score was invented."
                evaluation.completed_at = datetime.now(timezone.utc)
                db.commit()
                return evaluation.status
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()
