import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class Scripture(Base):
    __tablename__ = "scriptures"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapters: Mapped[list["Chapter"]] = relationship(back_populates="scripture")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="scripture")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scripture_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("scriptures.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scripture: Mapped[Scripture] = relationship(back_populates="chapters")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="chapter")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    scripture_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("scriptures.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    shloka_number: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    sanskrit_text: Mapped[str] = mapped_column(Text, nullable=False)
    transliteration: Mapped[str] = mapped_column(Text, default="")
    meaning: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str] = mapped_column(Text, default="")
    translations: Mapped[dict | list | None] = mapped_column(JSONType, nullable=True)
    daily_application: Mapped[str] = mapped_column(Text, default="")
    word_meanings: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    reference_audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    word_audio_timings: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    reference_audio_content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reference_audio_byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference_audio_filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="guru_provided", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    scripture: Mapped[Scripture] = relationship(back_populates="lessons")
    chapter: Mapped[Chapter | None] = relationship(back_populates="lessons")
    audits: Mapped[list["LessonAudit"]] = relationship(back_populates="lesson")
    versions: Mapped[list["LessonVersion"]] = relationship(back_populates="lesson")


class LessonAudit(Base):
    __tablename__ = "lesson_audits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_sanskrit: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lesson: Mapped[Lesson] = relationship(back_populates="audits")


class LessonVersion(Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (UniqueConstraint("lesson_id", "version_number", name="uq_lesson_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    shloka_number: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    sanskrit_text: Mapped[str] = mapped_column(Text, nullable=False)
    transliteration: Mapped[str] = mapped_column(Text, default="")
    meaning: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str] = mapped_column(Text, default="")
    translations: Mapped[dict | list | None] = mapped_column(JSONType, nullable=True)
    word_meanings: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    daily_application: Mapped[str] = mapped_column(Text, default="")
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lesson: Mapped[Lesson] = relationship(back_populates="versions")
