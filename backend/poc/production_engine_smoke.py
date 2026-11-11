"""Run the production ASR and known-text aligner on the nine Guru reference clips.

This is a smoke/compatibility check only: Guru recordings are not learner samples,
and generated timestamps are not timing or pronunciation validation data.
"""
from __future__ import annotations

import json
import sys
import io
import wave
from pathlib import Path

sys.path.insert(0, "/app")

from app.services.audio_preprocess import preprocess_audio
from app.services.engines.base import EngineContext
from app.services.engines.registry import get_alignment_engine, get_transcription_engine


content = json.loads(Path("/content/Evaluation.json").read_text(encoding="utf-8"))
asr = get_transcription_engine()
aligner = get_alignment_engine()
results = []
for lesson in content["lessons"]:
    audio_path = Path("/guru") / f'{lesson["lesson_id"]}.ogg'
    raw = audio_path.read_bytes()
    processed = preprocess_audio(raw, audio_path.name, "audio/ogg")
    with wave.open(io.BytesIO(processed.data), "rb") as normalized_wav:
        duration_ms = round(1000 * normalized_wav.getnframes() / normalized_wav.getframerate())
    context = EngineContext(
        lesson_slug=lesson["lesson_id"],
        reference_tokens=lesson["reference_words"],
        learner_filename=audio_path.name,
        learner_audio=processed,
        guru_audio=None,
        guru_storage_key=None,
        learner_storage_key="local-smoke-test",
        recitation_profile="Shared/common reference",
    )
    transcript = asr.transcribe(context)
    aligned = aligner.forced_align(context, lesson["reference_words"])
    results.append({
        "lesson_id": lesson["lesson_id"],
        "audio_status": processed.status,
        "duration_ms": duration_ms,
        "transcript_status": transcript.status,
        "transcript": " ".join(transcript.tokens or []),
        "alignment_status": aligned.get("status"),
        "aligned_word_count": len(aligned.get("words", [])),
        "aligned_akshara_count": len(aligned.get("aksharas", [])),
        "alignment_reason": aligned.get("reason"),
        "pronunciation_assessment": "unavailable",
    })

print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
