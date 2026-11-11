from uuid import UUID

from pydantic import BaseModel, Field


class ScriptureIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    sort_order: int = 0
    is_published: bool = True


class ChapterIn(BaseModel):
    scripture_id: UUID
    title: str = Field(min_length=1, max_length=200)
    sort_order: int = 0
    is_published: bool = True


class LessonIn(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    scripture_id: UUID
    chapter_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    shloka_number: str = Field(default="", max_length=80)
    canonical_reference: str = Field(min_length=1, max_length=200)
    sanskrit_text: str = Field(min_length=1)
    transliteration: str = ""
    meaning: str = Field(min_length=1)
    translation: str = ""
    translations: dict | list | None = None
    daily_application: str = ""
    word_meanings: list | None = None
    sort_order: int = 0
    confirm_guru_edit: bool = False
    edit_note: str = ""


class PublishIn(BaseModel):
    note: str = ""


class RestoreIn(BaseModel):
    confirm_guru_edit: bool = False
    edit_note: str = ""
