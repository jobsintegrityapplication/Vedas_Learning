"""Isolated Vedic Wav2Vec2 CTC ASR/known-text alignment benchmark.

This is a research harness, not a production pronunciation scorer. Forced
alignment scores indicate how the model fits a supplied transcript; without
Guru-reviewed timestamps they do not establish correctness or pronunciation.
"""
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
import torchaudio
from huggingface_hub import snapshot_download
from transformers import AutoModelForCTC, AutoProcessor


MODEL_ID = "chiranjeevisagi/wav2vec2-vedic-aligner"
SAMPLE_RATE = 16000
BLANK_ID = 0  # Explicitly documented by this checkpoint; <pad> is not CTC blank.


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    output = []
    for char in text:
        cp = ord(char)
        if cp in {0x0951, 0x0952} or 0x1CD0 <= cp <= 0x1CFF:
            output.append(" ")
        elif unicodedata.category(char)[0] in {"L", "M"}:
            output.append(char)
        elif char.isspace():
            output.append(" ")
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


def normalize_audio(path: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = Path(temp_dir) / "mono_16k.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), str(wav_path)],
            check=True,
        )
        signal, rate = sf.read(wav_path, dtype="float32", always_2d=False)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    if rate != SAMPLE_RATE:
        raise ValueError(f"Expected {SAMPLE_RATE} Hz after conversion, got {rate}")
    return signal


def grapheme_clusters(text: str) -> list[str]:
    """Unicode grapheme approximation for Devanagari aksharas (not phonemes)."""
    clusters: list[str] = []
    for char in text:
        if not clusters:
            clusters.append(char)
        elif unicodedata.category(char).startswith("M") or char in {"\u200c", "\u200d"}:
            clusters[-1] += char
        elif clusters[-1].endswith(("\u094d", "\u200d")):
            clusters[-1] += char
        else:
            clusters.append(char)
    return clusters


def load_model(model_id: str, cache_dir: Path | None):
    kwargs = {"cache_dir": str(cache_dir)} if cache_dir else {}
    model_path = snapshot_download(model_id, cache_dir=str(cache_dir) if cache_dir else None)
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCTC.from_pretrained(model_path, local_files_only=True).to("cpu").eval()
    return processor, model, Path(model_path)


def decode_ctc(log_probs: torch.Tensor, processor) -> str:
    vocab = processor.tokenizer.get_vocab()
    reverse = {int(idx): token for token, idx in vocab.items()}
    frame_ids = log_probs.argmax(dim=-1).tolist()
    pieces = []
    previous = None
    for token_id in frame_ids:
        if token_id != previous and token_id != BLANK_ID:
            token = reverse.get(token_id, "")
            if token not in {"<s>", "<pad>", "</s>", "<unk>"}:
                pieces.append(" " if token == processor.tokenizer.word_delimiter_token else token)
        previous = token_id
    return " ".join("".join(pieces).split())


def align_word_spans(text: str, labels: list[int], path: torch.Tensor, frame_log_probs: torch.Tensor,
                     frame_duration_ms: float, processor) -> tuple[list[dict], list[dict]]:
    vocab = processor.tokenizer.get_vocab()
    reverse = {int(idx): token for token, idx in vocab.items()}
    token_frames: dict[int, list[int]] = {i: [] for i in range(len(labels))}
    # Recover target index by scanning the CTC path with its emission score.
    # TorchAudio returns the chosen label at each frame; repeated target labels
    # are disambiguated by the dynamic-programming path and target order.
    target_pos = 0
    after_blank = False
    for frame, raw_id in enumerate(path.tolist()):
        token_id = int(raw_id)
        if target_pos >= len(labels):
            continue
        if token_id == BLANK_ID:
            after_blank = True
            continue
        if (after_blank and target_pos + 1 < len(labels)
                and labels[target_pos + 1] == labels[target_pos] == token_id):
            target_pos += 1
        if token_id == labels[target_pos]:
            token_frames[target_pos].append(frame)
        elif target_pos + 1 < len(labels) and token_id == labels[target_pos + 1]:
            target_pos += 1
            token_frames[target_pos].append(frame)
        after_blank = False

    token_records = []
    for i, label in enumerate(labels):
        frames = token_frames[i]
        token = reverse.get(label, "")
        if frames:
            token_records.append({
                "target_index": i,
                "token": token,
                "start_ms": round(frames[0] * frame_duration_ms, 1),
                "end_ms": round((frames[-1] + 1) * frame_duration_ms, 1),
                "mean_token_posterior": round(float(frame_log_probs[frames, label].exp().mean().item()), 4),
                "frame_count": len(frames),
            })
        else:
            token_records.append({"target_index": i, "token": token, "status": "unaligned"})

    # Group token timings by the processor's word delimiter. This is still a
    # known-text forced fit, not proof that the uttered word was correct.
    words: list[dict] = []
    current = []
    for record in token_records:
        if record.get("token") == processor.tokenizer.word_delimiter_token:
            if current:
                words.append(_summarize_word(current))
                current = []
        else:
            current.append(record)
    if current:
        words.append(_summarize_word(current))

    # Aggregate character-token timings into Unicode grapheme clusters. This is
    # an orthographic akshara approximation, not a phoneme/GOP judgment.
    aksharas: list[dict] = []
    word_index = 0
    current_akshara_index = 0
    for source_word in normalize(text).split():
        clusters = grapheme_clusters(source_word)
        word_tokens = []
        while current_akshara_index < len(token_records):
            token_record = token_records[current_akshara_index]
            if token_record.get("token") == processor.tokenizer.word_delimiter_token:
                current_akshara_index += 1
                break
            word_tokens.append(token_record)
            current_akshara_index += 1
        token_offset = 0
        for cluster in clusters:
            cluster_tokens = word_tokens[token_offset:token_offset + len(cluster)]
            token_offset += len(cluster)
            aligned_cluster_tokens = [token for token in cluster_tokens if "start_ms" in token]
            aksharas.append({
                "word": source_word,
                "akshara": cluster,
                "start_ms": min((token["start_ms"] for token in aligned_cluster_tokens), default=None),
                "end_ms": max((token["end_ms"] for token in aligned_cluster_tokens), default=None),
                "coverage": round(len(aligned_cluster_tokens) / max(1, len(cluster_tokens)), 4),
                "mean_token_posterior": (
                    round(sum(token["mean_token_posterior"] for token in aligned_cluster_tokens) / len(aligned_cluster_tokens), 4)
                    if aligned_cluster_tokens else None
                ),
                "status": "aligned" if aligned_cluster_tokens else "unaligned",
            })
        word_index += 1
    return words, aksharas


def _summarize_word(tokens: list[dict]) -> dict:
    aligned = [token for token in tokens if "start_ms" in token]
    return {
        "text": "".join(token.get("token", "") for token in tokens),
        "status": "aligned" if aligned else "unaligned",
        "start_ms": min((item["start_ms"] for item in aligned), default=None),
        "end_ms": max((item["end_ms"] for item in aligned), default=None),
        "coverage": round(len(aligned) / max(1, len(tokens)), 4),
        "mean_token_posterior": round(sum(item["mean_token_posterior"] for item in aligned) / len(aligned), 4) if aligned else None,
    }


def evaluate_one(item: dict, processor, model) -> dict:
    audio_path = Path(item["audio_file_path"])
    audio = normalize_audio(audio_path)
    inputs = processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True)
    started = time.perf_counter()
    with torch.inference_mode():
        logits = model(input_values=inputs.input_values).logits[0]
    inference_ms = round((time.perf_counter() - started) * 1000, 1)
    log_probs = torch.log_softmax(logits, dim=-1)

    reference = normalize(item["source_text"])
    encoded = processor.tokenizer(reference, add_special_tokens=False).input_ids
    if not encoded:
        raise ValueError(f"No alignable target labels for {item['lesson_id']}")
    token_strings = processor.tokenizer.convert_ids_to_tokens(encoded)
    round_trip = "".join(" " if token == processor.tokenizer.word_delimiter_token else token for token in token_strings)
    if normalize(round_trip) != reference:
        raise ValueError(f"Tokenizer round-trip changed Sanskrit reference for {item['lesson_id']}")
    if BLANK_ID in encoded:
        raise ValueError(f"Reference for {item['lesson_id']} encoded the documented CTC blank ID")
    if max(encoded) >= log_probs.shape[-1]:
        raise ValueError(f"Target token id exceeds CTC vocabulary for {item['lesson_id']}")

    forced_labels, frame_scores = torchaudio.functional.forced_align(
        log_probs.unsqueeze(0),
        torch.tensor([encoded], dtype=torch.int32),
        input_lengths=torch.tensor([log_probs.shape[0]], dtype=torch.int32),
        target_lengths=torch.tensor([len(encoded)], dtype=torch.int32),
        blank=BLANK_ID,
    )
    forced_path = forced_labels[0]
    word_spans, word_aksharas = align_word_spans(
        reference, encoded, forced_path, log_probs, len(audio) * 1000 / SAMPLE_RATE / log_probs.shape[0], processor
    )
    transcript = decode_ctc(log_probs, processor)
    hypothesis = normalize(transcript)
    ref_chars = list(reference.replace(" ", ""))
    hyp_chars = list(hypothesis.replace(" ", ""))
    ref_words, hyp_words = reference.split(), hypothesis.split()
    duration_ms = round(len(audio) * 1000 / SAMPLE_RATE, 1)
    return {
        "lesson_id": item["lesson_id"],
        "audio_sha256": hashlib.sha256(audio_path.read_bytes()).hexdigest(),
        "audio_duration_ms": duration_ms,
        "inference_ms_cpu": inference_ms,
        "reference_text": reference,
        "asr_transcript_candidate": transcript,
        "cer": edit_distance(ref_chars, hyp_chars) / max(1, len(ref_chars)),
        "whitespace_wer": edit_distance(ref_words, hyp_words) / max(1, len(ref_words)),
        "ctc_alignment": {
            "status": "completed_candidate",
            "blank_id": BLANK_ID,
            "source_frame_count": int(log_probs.shape[0]),
            "target_label_count": len(encoded),
            "mean_forced_frame_log_probability": round(float(frame_scores[0].mean().item()), 4),
            "frame_score_interpretation": "Uncalibrated model fit diagnostic; not pronunciation accuracy or a percent score.",
            "words": word_spans,
            "aksharas": word_aksharas,
            "interpretation": "Forced alignment fits the supplied text to the audio; low or high fit is not independently validated pronunciation accuracy.",
        },
        "guru_transcript_review_status": "pending",
        "manual_timing_review_status": "pending",
        "pronunciation_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()

    processor, model, model_path = load_model(args.model_id, args.cache_dir)
    rows = [evaluate_one(item, processor, model) for item in json.loads(args.evaluation.read_text(encoding="utf-8"))["lessons"]]
    model_sha = None
    weight_files = list(model_path.glob("*.safetensors")) + list(model_path.glob("pytorch_model*.bin"))
    if weight_files:
        model_sha = {str(path.name): hashlib.sha256(path.read_bytes()).hexdigest() for path in weight_files}
    output = {
        "engine": "wav2vec2-vedic-aligner-ctc",
        "model_repository": args.model_id,
        "model_card_claimed_license": "Apache-2.0",
        "model_checkpoint_revision": getattr(model.config, "_commit_hash", None),
        "model_weight_sha256": model_sha,
        "sample_rate_hz": SAMPLE_RATE,
        "ctc_blank_id": BLANK_ID,
        "metric_scope": "asr_and_known_text_ctc_forced_alignment_candidate_only",
        "accuracy_warning": "Guru transcript and manual timing review are pending. Forced fit and ASR transcript do not equal pronunciation scores.",
        "mean_cer": sum(row["cer"] for row in rows) / max(1, len(rows)),
        "mean_whitespace_wer": sum(row["whitespace_wer"] for row in rows) / max(1, len(rows)),
        "mean_inference_ms_cpu": sum(row["inference_ms_cpu"] for row in rows) / max(1, len(rows)),
        "results": rows,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
