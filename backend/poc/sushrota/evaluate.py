"""Isolated Su-śrotā transcript benchmark. Never emits pronunciation scores."""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # Keep Unicode letters/marks (including virama and vowel signs) and make
    # punctuation, digits, and symbols token boundaries across Indic scripts.
    normalized: list[str] = []
    for char in text:
        codepoint = ord(char)
        if char in {"ऽ", "ॐ"} or 0x0951 <= codepoint <= 0x0952 or 0x1CD0 <= codepoint <= 0x1CFF:
            normalized.append(" ")
        elif unicodedata.category(char)[0] in {"L", "M"}:
            normalized.append(char)
        else:
            normalized.append(" ")
    return " ".join("".join(normalized).split())


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i]
        for j, b in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def error_rate(reference: str, hypothesis: str, *, characters: bool) -> float:
    ref = normalize(reference).replace(" ", "") if characters else normalize(reference)
    hyp = normalize(hypothesis).replace(" ", "") if characters else normalize(hypothesis)
    left = list(ref) if characters else ref.split()
    right = list(hyp) if characters else hyp.split()
    return edit_distance(left, right) / max(1, len(left))


def align_words(reference: str, hypothesis_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sequence-align reference words to approximate CTC transcript word spans."""
    ref = normalize(reference).split()
    hyp = [normalize(str(row["word"])) for row in hypothesis_words]
    costs = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    steps = [[""] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(1, len(ref) + 1):
        costs[i][0], steps[i][0] = i, "omit"
    for j in range(1, len(hyp) + 1):
        costs[0][j], steps[0][j] = j, "insert"
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            same = ref[i - 1] == hyp[j - 1]
            options = [(costs[i - 1][j - 1] + (not same), "match" if same else "substitute"),
                       (costs[i - 1][j] + 1, "omit"), (costs[i][j - 1] + 1, "insert")]
            costs[i][j], steps[i][j] = min(options, key=lambda item: item[0])
    aligned: list[dict[str, Any]] = []
    i, j = len(ref), len(hyp)
    while i or j:
        operation = steps[i][j]
        if operation in {"match", "substitute"}:
            aligned.append({"reference_word": ref[i - 1], "recognized_word": hyp[j - 1],
                            "status": operation, "start_ms": hypothesis_words[j - 1]["start_ms"],
                            "end_ms": hypothesis_words[j - 1]["end_ms"]})
            i -= 1
            j -= 1
        elif operation == "omit":
            aligned.append({"reference_word": ref[i - 1], "recognized_word": None,
                            "status": "omitted", "start_ms": None, "end_ms": None})
            i -= 1
        else:
            aligned.append({"reference_word": None, "recognized_word": hyp[j - 1],
                            "status": "inserted", "start_ms": hypothesis_words[j - 1]["start_ms"],
                            "end_ms": hypothesis_words[j - 1]["end_ms"]})
            j -= 1
    return list(reversed(aligned))


def transcribe(checkpoint: Path, audio_paths: list[Path]) -> list[dict[str, Any]]:
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from nemo.collections.asr.models import EncDecHybridRNNTCTCBPEModel
    except ImportError as exc:
        raise SystemExit(
            "Missing isolated POC dependency. Install numpy, soundfile, torch, and compatible nemo_toolkit[asr]."
        ) from exc

    model = EncDecHybridRNNTCTCBPEModel.restore_from(str(checkpoint), map_location="cuda" if torch.cuda.is_available() else "cpu").eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    offset, vocab_size, blank = 4096, 256, 5632
    tokenizer = model.tokenizer.tokenizers_dict["sa"]
    outputs: list[dict[str, Any]] = []
    for path in audio_paths:
        audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
        if sample_rate != 16000 or audio.ndim != 1:
            raise ValueError(f"{path}: expected mono 16 kHz WAV, got {sample_rate} Hz / shape {audio.shape}")
        signal = torch.from_numpy(np.asarray(audio, dtype=np.float32)).unsqueeze(0).to(device)
        lengths = torch.tensor([signal.shape[1]], device=device)
        with torch.inference_mode():
            encoded, _ = model.forward(input_signal=signal, input_signal_length=lengths)
            logits = model.ctc_decoder(encoder_output=encoded)[0].float().cpu().numpy()
        columns = [blank, *range(offset, offset + vocab_size)]
        selected = logits[:, columns]
        selected -= np.logaddexp.reduce(selected, axis=1, keepdims=True)
        ids = selected.argmax(axis=1)
        token_spans: list[dict[str, Any]] = []
        previous = -1
        run_start = 0
        for frame, raw_id in enumerate(ids):
            token_id = int(raw_id)
            if token_id != previous and previous != -1 and previous != 0:
                token = tokenizer.ids_to_tokens([previous - 1])[0]
                token_spans.append({"token": token, "first_frame": run_start, "last_frame": frame - 1})
            if token_id != previous and token_id != 0:
                run_start = frame
            previous = token_id
        if previous > 0:
            token_spans.append({"token": tokenizer.ids_to_tokens([previous - 1])[0],
                                "first_frame": run_start, "last_frame": len(ids) - 1})
        duration_ms = len(audio) * 1000 / sample_rate
        words: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for span in token_spans:
            piece = span["token"]
            starts_word = piece.startswith("▁")
            if starts_word and current is not None:
                words.append(current)
                current = None
            if current is None:
                current = {"word": "", "start_ms": round(span["first_frame"] * duration_ms / len(ids)),
                           "end_ms": round((span["last_frame"] + 1) * duration_ms / len(ids))}
            current["word"] += piece.replace("▁", "")
            current["end_ms"] = round((span["last_frame"] + 1) * duration_ms / len(ids))
        if current is not None:
            words.append(current)
        outputs.append({"transcript": " ".join(item["word"] for item in words), "word_segments": words})
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows: list[dict[str, Any]] = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not rows:
        raise SystemExit("Manifest has no audio rows")
    audio = [Path(row["audio_path"]) for row in rows]
    hypotheses = transcribe(args.checkpoint, audio)
    results = []
    for row, hypothesis_result in zip(rows, hypotheses):
        reference = row["reference_text"]
        hypothesis = hypothesis_result["transcript"]
        results.append({
            "lesson_id": row["lesson_id"],
            "reference_text": reference,
            "transcript": hypothesis,
            "cer": error_rate(reference, hypothesis, characters=True),
            "wer": error_rate(reference, hypothesis, characters=False),
            "approximate_ctc_word_alignment": align_words(reference, hypothesis_result["word_segments"]),
            "pronunciation_assessment": "not_evaluated",
        })
    output = {
        "engine": "sushrota-indicconformer-ctc",
        "metric_scope": "transcription_only",
        "results": results,
        "mean_cer": sum(row["cer"] for row in results) / len(results),
        "mean_wer": sum(row["wer"] for row in results) / len(results),
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
