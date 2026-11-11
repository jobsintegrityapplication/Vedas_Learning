from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Evaluation, Recording


def line_has_accepted_match(db: Session, *, user_id, lesson_id, line_index: int) -> bool:
    """Return true only when this learner has an accepted, threshold-passing attempt."""
    reports = db.scalars(
        select(Evaluation.report)
        .join(Recording, Recording.id == Evaluation.recording_id)
        .where(
            Recording.user_id == user_id,
            Recording.lesson_id == lesson_id,
            Recording.line_index == line_index,
        )
    ).all()
    threshold = get_settings().word_match_pass_threshold_percent
    for report in reports:
        if not isinstance(report, dict) or report.get("accepted") is not True:
            continue
        word_accuracy = report.get("word_accuracy")
        if not isinstance(word_accuracy, dict):
            continue
        match_percent = word_accuracy.get("match_percent")
        if (isinstance(match_percent, (int, float))
                and match_percent >= threshold
                and word_accuracy.get("meets_word_threshold") is True
                and report.get("reference_audio_status") == "available"):
            return True
    return False
