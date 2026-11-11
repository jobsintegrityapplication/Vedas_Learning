import json
from pathlib import Path


def test_multilingual_draft_has_a_complete_lesson_and_language_map():
    root = Path(__file__).resolve().parents[2]
    asset = json.loads(
        (root / "mobile" / "assets" / "rigveda_multilingual_content_draft.json").read_text(encoding="utf-8")
    )
    lessons = json.loads((root / "content" / "rigveda_lessons.json").read_text(encoding="utf-8"))
    records = {row["lesson_slug"]: row for row in asset["records"]}
    lesson_by_slug = {row["id"]: row for row in lessons}

    assert set(records) == {row["id"] for row in lessons}
    assert "DRAFT_REQUIRES_SANSKRIT_AND_NATIVE_LANGUAGE_REVIEW" in {
        row["content_status"] for row in records.values()
    }
    for record in records.values():
        assert set(record["languages"]) == {
            "sa", "kn", "hi", "en", "te", "ta", "ml", "mr", "bn", "gu", "pa", "or"
        }
        assert all(language["mantra_text"].strip() for language in record["languages"].values())
        line_count = len(lesson_by_slug[record["lesson_slug"]]["sanskrit"].splitlines())
        if line_count > 1:
            assert all(
                language["mantra_text"].count("।") + 1 == line_count
                for language in record["languages"].values()
            )
