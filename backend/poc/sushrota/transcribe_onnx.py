"""Local ONNX transcription benchmark for the nine Guru reference clips.

Transcription output is ASR evidence only. It is not Guru-verified ground truth
and must not be used as a pronunciation or svara score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    normalized = []
    for char in text:
        codepoint = ord(char)
        if codepoint in {0x0951, 0x0952} or 0x1CD0 <= codepoint <= 0x1CFF:
            normalized.append(" ")
        elif unicodedata.category(char)[0] in {"L", "M"}:
            normalized.append(char)
        else:
            normalized.append(" ")
    return " ".join("".join(normalized).split())


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def transcribe(audio_path: Path, model_dir: Path) -> str:
    import numpy as np
    import onnxruntime as ort
    import soundfile as sf
    from scipy.signal import resample_poly

    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = Path(temp_dir) / "mono_16k.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(audio_path), "-ac", "1", "-ar", "16000", str(wav_path)],
            check=True,
        )
        signal, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    if sample_rate != 16000:
        signal = resample_poly(signal, 16000, sample_rate).astype(np.float32)

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    preprocessor = ort.InferenceSession(str(model_dir / "preprocessor.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
    model = ort.InferenceSession(str(model_dir / "sushrota_sanskrit_ctc_int8.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
    features, feature_lengths = preprocessor.run(None, {
        "audio_signal": signal[np.newaxis, :].astype(np.float32),
        "length": np.asarray([len(signal)], dtype=np.int64),
    })
    logits = model.run(None, {"audio_signal": features, "length": feature_lengths})[0]
    vocab_payload = json.loads((model_dir / "sanskrit_vocab.json").read_text(encoding="utf-8"))
    vocab = vocab_payload.get("vocab", vocab_payload) if isinstance(vocab_payload, dict) else vocab_payload
    ids = np.argmax(logits[0], axis=-1).tolist()
    output: list[str] = []
    previous = -1
    for raw_id in ids:
        token_id = int(raw_id)
        if token_id != previous and token_id != 0:
            token = vocab[token_id] if isinstance(vocab, list) else vocab.get(str(token_id), vocab.get(token_id, ""))
            output.append(str(token))
        previous = token_id
    return "".join(output).replace("▁", " ").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.evaluation.read_text(encoding="utf-8"))
    rows = []
    for item in payload["lessons"]:
        transcript = transcribe(Path(item["audio_file_path"]), args.model_dir)
        reference = normalize(item["source_text"])
        hypothesis = normalize(transcript)
        reference_chars, hypothesis_chars = list(reference.replace(" ", "")), list(hypothesis.replace(" ", ""))
        reference_words, hypothesis_words = reference.split(), hypothesis.split()
        rows.append({
            "lesson_id": item["lesson_id"],
            "transcript_candidate": transcript,
            "candidate_words": hypothesis_words,
            "reference_words": item["reference_words"],
            "reference_text": item["source_text"],
            "cer": edit_distance(reference_chars, hypothesis_chars) / max(1, len(reference_chars)),
            "wer": edit_distance(reference_words, hypothesis_words) / max(1, len(reference_words)),
            "word_alignment_status": "not_forced_aligned",
            "guru_review_status": "pending",
        })
    args.output.write_text(json.dumps({
        "engine": "sushrota-indicconformer-ctc-onnx-int8",
        "model_repository": "https://huggingface.co/gnumanth/sushrota-sanskrit-asr-onnx",
        "model_version_claimed_by_repository": "v13b",
        "model_sha256": hashlib.sha256((args.model_dir / "sushrota_sanskrit_ctc_int8.onnx").read_bytes()).hexdigest(),
        "metric_scope": "transcription_only",
        "accuracy_warning": "Candidate transcripts require Guru review; transcript similarity is not pronunciation accuracy.",
        "mean_cer": sum(row["cer"] for row in rows) / max(1, len(rows)),
        "mean_whitespace_wer": sum(row["wer"] for row in rows) / max(1, len(rows)),
        "results": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
