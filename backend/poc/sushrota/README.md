# Su-śrotā local proof of concept

This is an isolated ASR benchmark harness. It does not change the production Guru audio or speech-evaluation pipeline and does not produce pronunciation scores.

## Compatibility and limits

The upstream checkpoint is a NeMo `EncDecHybridRNNTCTCBPEModel`, about 129M parameters. The published decode path uses the Sanskrit CTC slice (blank id 5632, token ids 4096–4351), the `sa` SentencePiece tokenizer, and 16 kHz mono float32 audio. Convert OGG recordings to mono 16 kHz WAV with ffmpeg before running this harness. A CUDA GPU is recommended for practical inference; CPU inference may be substantially slower. Install a NeMo version compatible with the checkpoint and its PyTorch/CUDA dependencies in a separate environment; do not add these dependencies to the production image for this POC.

The model repository asks users to observe IndicConformer's base license terms but does not state a separate fine-tuned checkpoint license in its model card. Resolve this with the model owner before commercial deployment or redistribution. Pin a reviewed checkpoint revision and record its checksum before evaluating.

## Run

Prepare `manifest.json` as an array of `{ "lesson_id": "...", "reference_text": "...", "audio_path": "..." }` rows. Audio paths should be 16 kHz mono WAV. Install `numpy`, `soundfile`, `torch`, and the compatible `nemo_toolkit[asr]` package in a disposable virtual environment, download the exact checkpoint from Hugging Face, then run:

```powershell
python backend/poc/sushrota/evaluate.py --checkpoint .\sushrota_sanskrit_asr_v13b.nemo --manifest .\manifest.json --output .\sushrota-results.json
```

The output records transcript, reference text, normalized CER and whitespace WER per clip and overall, plus a reference-to-transcript edit alignment. `approximate_ctc_word_alignment` estimates word spans by grouping greedy CTC token emissions onto the model frame grid; it is useful for triage, but is not a validated forced aligner or phonetic ground truth. It must not be presented as pronunciation, akṣara alignment, vowel-length, consonant, svara, pitch, or validated timing scores. This harness intentionally reports no such findings.

The supplied Guru clips can be used as a first ASR smoke/evaluation set once their lesson mapping and exact Sanskrit text have been reviewed. Student-vs-Guru pronunciation validation additionally requires consented student recordings, an independently validated aligner/phonetic assessor, and Guru-reviewed labels; ASR alone cannot provide that evidence.

## Local ONNX benchmark for the nine mapped clips

`content/Evaluation.json` contains the nine mapped audio paths, source-text word lists, and the locally generated ASR candidates. The candidate report is `content/Evaluation_ASR_candidates.json`. Audio bytes in `C:/Users/ZMIT/Downloads` and their mapped app assets were checked against the same SHA-256 values before inference.

For a repeatable CPU run from the repository root:

```powershell
docker build -f backend/poc/sushrota/Dockerfile.benchmark -t veda-sushrota-benchmark .
docker run --rm --entrypoint python -v "${PWD}:/workspace" -w /workspace veda-sushrota-benchmark backend/poc/sushrota/download_onnx_model.py --model-dir backend/poc/sushrota/models
docker run --rm --entrypoint python -v "${PWD}:/workspace" -w /workspace veda-sushrota-benchmark backend/poc/sushrota/transcribe_onnx.py --evaluation content/Evaluation.json --model-dir backend/poc/sushrota/models --output content/Evaluation_ASR_candidates.json
```

The model cache is ignored by Git and Docker and is not shipped in the production app image. Candidate transcripts are stored separately from the source text and require Guru review. The nine-clip local run measured 7.4% mean CER after the model's accent/punctuation normalization and 74.3% mean whitespace WER. The latter is dominated by Sanskrit sandhi/token boundaries; clips 4 and 9 also have substantial character-level errors. These results are insufficient to enable automatic lesson acceptance. The production configuration remains `EVALUATION_ENGINE=none`. No vowel-length, consonant-articulation, pronunciation, or svara findings are produced.
