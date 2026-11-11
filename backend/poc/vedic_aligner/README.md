# Vedic Wav2Vec2 known-text alignment proof of concept

This isolated benchmark evaluates `chiranjeevisagi/wav2vec2-vedic-aligner` on the nine bundled Guru recordings. It does not change production dependencies or enable evaluation in the app.

The model card describes a Wav2Vec2 CTC checkpoint fine-tuned on Vedavani and teacher recitations, with a 67-character Devanagari vocabulary, 16 kHz audio, and CTC blank ID `0` (`<s>`, not `<pad>`). Its card states Apache-2.0. Torchaudio 2.6.0 is pinned in the benchmark environment because later versions removed `functional.forced_align`.

The script reports (a) greedy ASR transcript candidates, (b) CER/whitespace WER against the current unreviewed lesson source, and (c) known-text CTC forced word and orthographic akṣara timing candidates. A forced fit always attempts to place the supplied labels; its frame log probability is an uncalibrated fit diagnostic. It is not transcript correctness, pronunciation accuracy, a GOP grade, or Vedic svara. No Guru-reviewed transcript/timing labels or learner recitations are present, so the benchmark cannot measure false positives/negatives, timing error, or actual pronunciation-scoring accuracy.

## Run

```powershell
docker build -f backend/poc/vedic_aligner/Dockerfile.benchmark -t veda-vedic-aligner-benchmark .
docker run --rm --entrypoint python -v "${PWD}:/workspace" -v "${PWD}/backend/poc/vedic_aligner/model_cache:/models" -w /workspace veda-vedic-aligner-benchmark backend/poc/vedic_aligner/evaluate.py --evaluation content/Evaluation.json --cache-dir /models --output content/Evaluation_Vedic_aligner_candidates.json
```

Weights are cached locally in the ignored `model_cache/` directory. The JSON report is a candidate research artifact and must not drive lesson acceptance until the source text, word boundaries, timing, and student pronunciation findings have been independently reviewed and validated.
