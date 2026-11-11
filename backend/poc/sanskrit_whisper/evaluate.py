"""Isolated Sanskrit Whisper transcription benchmark for the nine Guru clips."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import snapshot_download
from transformers import WhisperForConditionalGeneration, WhisperProcessor


MODEL_ID = "rverma251/sanskrit-whisper-asr"
SAMPLE_RATE = 16000


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    output = []
    for char in text:
        cp = ord(char)
        if cp in {0x0951, 0x0952} or 0x1CD0 <= cp <= 0x1CFF:
            output.append(" ")
        elif unicodedata.category(char)[0] in {"L", "M"}:
            output.append(char)
        else:
            output.append(" ")
    return " ".join("".join(output).split())


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def load_audio(path: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as temp_dir:
        wav = Path(temp_dir) / "audio_16k.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), str(wav)],
            check=True,
        )
        samples, rate = sf.read(wav, dtype="float32", always_2d=False)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    if rate != SAMPLE_RATE:
        raise ValueError(f"Expected {SAMPLE_RATE} Hz after conversion, got {rate}")
    return samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default=MODEL_ID)
    args = parser.parse_args()

    model_path = Path(snapshot_download(args.model_id, cache_dir=str(args.cache_dir)))
    processor = WhisperProcessor.from_pretrained(model_path, local_files_only=True)
    model = WhisperForConditionalGeneration.from_pretrained(model_path, local_files_only=True).to("cpu").eval()
    # Matches the model card's stated generation setup. The checkpoint uses
    # Hindi's Whisper language token for Sanskrit output; this is a limitation.
    model.generation_config.language = "hindi"
    model.generation_config.task = "transcribe"

    results = []
    for item in json.loads(args.evaluation.read_text(encoding="utf-8"))["lessons"]:
        path = Path(item["audio_file_path"])
        samples = load_audio(path)
        features = processor.feature_extractor(samples, sampling_rate=SAMPLE_RATE, return_tensors="pt").input_features
        started = time.perf_counter()
        with torch.inference_mode():
            predicted = model.generate(features, max_new_tokens=256)
        inference_ms = round((time.perf_counter() - started) * 1000, 1)
        transcript = processor.tokenizer.batch_decode(predicted, skip_special_tokens=True)[0]
        reference = normalize(item["source_text"])
        hypothesis = normalize(transcript)
        reference_chars, hypothesis_chars = list(reference.replace(" ", "")), list(hypothesis.replace(" ", ""))
        reference_words, hypothesis_words = reference.split(), hypothesis.split()
        results.append({
            "lesson_id": item["lesson_id"],
            "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "audio_duration_ms": round(len(samples) * 1000 / SAMPLE_RATE, 1),
            "inference_ms_cpu": inference_ms,
            "reference_text_unreviewed": reference,
            "asr_transcript_candidate": transcript,
            "cer": edit_distance(reference_chars, hypothesis_chars) / max(1, len(reference_chars)),
            "whitespace_wer": edit_distance(reference_words, hypothesis_words) / max(1, len(reference_words)),
            "review_status": "pending_guru_review",
            "word_alignment": "not_provided",
            "pronunciation_score": None,
        })

    weights = list(model_path.glob("model.safetensors")) + list(model_path.glob("pytorch_model*.bin"))
    payload = {
        "engine": "sanskrit-whisper-small-asr-candidate",
        "model_repository": args.model_id,
        "model_card_license": "Apache-2.0",
        "model_card_base": "openai/whisper-small",
        "model_card_training_data": "21,385 Sanskrit samples from AI4Bharat Rasa",
        "generation_language_token": "hindi (as specified by the model card)",
        "model_checkpoint_revision": getattr(model.config, "_commit_hash", None),
        "model_weight_sha256": {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in weights},
        "sample_rate_hz": SAMPLE_RATE,
        "metric_scope": "asr_candidate_only",
        "accuracy_warning": "Reference source text is unreviewed; transcription similarity is not pronunciation accuracy.",
        "mean_cer": sum(row["cer"] for row in results) / max(1, len(results)),
        "mean_whitespace_wer": sum(row["whitespace_wer"] for row in results) / max(1, len(results)),
        "mean_inference_ms_cpu": sum(row["inference_ms_cpu"] for row in results) / max(1, len(results)),
        "results": results,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
