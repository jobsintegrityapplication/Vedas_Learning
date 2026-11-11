import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    line_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recitation_profile: Mapped[str] = mapped_column(String(20), default="Kanchi", nullable=False)
    mantra_reference: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), default="audio/mp4")
    original_filename: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(40), default="learner", nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="recording", uselist=False)


class RecitationReferenceAudio(Base):
    __tablename__ = "recitation_reference_audio"
    __table_args__ = (UniqueConstraint("profile", "mantra_reference", "asset_kind", "word_order", name="uq_reference_audio_profile_mantra_kind_word"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    mantra_reference: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # full_mantra | word
    word_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    speaker_attribution: Mapped[str] = mapped_column(String(300), nullable=False)
    source_attribution: Mapped[str] = mapped_column(String(500), nullable=False)
    rights_status: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    rights_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    validation_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecitationTextVariant(Base):
    __tablename__ = "recitation_text_variants"
    __table_args__ = (UniqueConstraint("profile", "mantra_reference", name="uq_recitation_text_variant_profile_reference"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    mantra_reference: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    samhita_form: Mapped[str] = mapped_column(Text, nullable=False)
    padapatha_form: Mapped[str] = mapped_column(Text, nullable=False)
    padapatha_tokens: Mapped[list] = mapped_column(JSONType, nullable=False)
    phonetic_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    source_provenance: Mapped[dict] = mapped_column(JSONType, nullable=False)
    rights_status: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProgressiveMantraProgress(Base):
    __tablename__ = "progressive_mantra_progress"
    __table_args__ = (UniqueConstraint("user_id", "profile", "mantra_reference", name="uq_progressive_user_profile_mantra"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile: Mapped[str] = mapped_column(String(20), nullable=False)
    mantra_reference: Mapped[str] = mapped_column(String(32), nullable=False)
    unlocked_word_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_word_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    completed_word_orders: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    bookmarked: Mapped[bool] = mapped_column(default=False, nullable=False)
    combined_passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProgressiveMantraAttempt(Base):
    __tablename__ = "progressive_mantra_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile: Mapped[str] = mapped_column(String(20), nullable=False)
    mantra_reference: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    word_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_status: Mapped[str] = mapped_column(String(40), default="unavailable", nullable=False)
    report: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LessonLineProgress(Base):
    __tablename__ = "lesson_line_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", "line_index", name="uq_line_progress_user_lesson_line"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    line_index: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False, index=True)
    engine_id: Mapped[str] = mapped_column(String(80), default="none")
    engine_version: Mapped[str] = mapped_column(String(40), default="0")
    word_accuracy_status: Mapped[str] = mapped_column(String(40), default="unavailable")
    pronunciation_status: Mapped[str] = mapped_column(String(40), default="unavailable")
    svara_status: Mapped[str] = mapped_column(String(40), default="unavailable")
    alignment: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    hypothesis_tokens: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recording: Mapped[Recording] = relationship(back_populates="evaluation")


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_recording_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True)
    last_practiced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsageSession(Base):
    __tablename__ = "usage_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scripture_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("scriptures.id", ondelete="SET NULL"), nullable=True, index=True)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class GuruReferenceAudio(Base):
    __tablename__ = "guru_reference_audio"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), default="audio/wav")
    original_filename: Mapped[str] = mapped_column(String(200), default="")
    byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
