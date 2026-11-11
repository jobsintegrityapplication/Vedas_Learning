# Sanskrit Whisper ASR candidate benchmark

This candidate-only benchmark compares the Apache-2.0 `rverma251/sanskrit-whisper-asr` model against the nine bundled Guru clips. It is not used by the production app and produces no forced alignment or pronunciation score.

The model card reports a fine-tuned Whisper-small model trained on 21,385 AI4Bharat Rasa Sanskrit samples and specifies `language='hindi'` for generation. The benchmark follows that published configuration because Sanskrit is not a supported Whisper language token in the card's example; this remains a model limitation. The card's hosted inference provider is unavailable.

Run with the CPU-only benchmark image built for the Vedic aligner:

```powershell
docker run --rm --entrypoint python -v "${PWD}:/workspace" -v "${PWD}/backend/poc/sanskrit_whisper/model_cache:/models" -w /workspace veda-vedic-aligner-benchmark backend/poc/sanskrit_whisper/evaluate.py --evaluation content/Evaluation.json --cache-dir /models --output content/Evaluation_Sanskrit_whisper_candidates.json
```

CER and whitespace WER are reported only as ASR candidate metrics. The source text and model transcripts still need Guru review; these measures do not support pronunciation judgments.
