"""Create a non-authoritative G2P candidate sheet from Evaluation.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.services.sanskrit_g2p import transcribe_text_to_phonemes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
    rows = []
    for lesson in evaluation["lessons"]:
        candidate = transcribe_text_to_phonemes(lesson["source_text"])
        rows.append({
            "lesson_id": lesson["lesson_id"],
            "lesson_title": lesson["lesson_title"],
            "canonical_reference": lesson["canonical_reference"],
            "audio_file": lesson["audio_file_path"],
            "source_text_review_status": lesson.get("guru_transcript_review_status", "pending"),
            "g2p_candidate": candidate,
        })
    payload = {
        "purpose": "Provisional expected phoneme hypotheses from current lesson text; not audio analysis.",
        "status": "guru_review_required",
        "model_evaluation_eligible": False,
        "g2p_profile": rows[0]["g2p_candidate"]["profile_id"] if rows else None,
        "lessons": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "lesson_count": len(rows),
        "word_count": sum(len(row["g2p_candidate"]["words"]) for row in rows),
        "status_counts": {
            status: sum(row["g2p_candidate"]["status"] == status for row in rows)
            for status in {row["g2p_candidate"]["status"] for row in rows}
        },
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
