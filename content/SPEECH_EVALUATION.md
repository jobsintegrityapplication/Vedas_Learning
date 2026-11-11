# Sanskrit speech evaluation

Evaluation is keyed to the learner's selected recitation profile and mantra address. The worker requires an individually reviewed, rights-cleared profile Padapāṭha record before it compares words. It never falls back to the common lesson string or another profile. Kanchi, Sringeri, and Common token/phonetic references, full-mantra reference audio, and evaluations remain separate.

## Analysis contract

- Recognized source-backed word tokens are compared with the selected profile's ordered Padapāṭha tokens using edit alignment. Omissions, substitutions, and insertions are returned with target-specific practice guidance. Provider and confidence provenance are retained.
- A transcription provider may implement `forced_align(context, hypothesis_tokens)`. The result is accepted only when each word has an order, token, valid start/end times, and confidence from 0 to 1. Token edit alignment alone is never labeled forced alignment.
- Pronunciation providers can return acoustic findings for vowel length/duration, consonant place/manner/voicing, aspiration, visarga, anusvāra, and Vedic accent. A finding is surfaced only with a supported feature name, reference and observed values, confidence, learner-audio time span, and correction guidance. Unsupported or incomplete findings are withheld.
- Vedic accent assessment remains unavailable unless a specialist svara provider and reviewed profile accent metadata are available. Its results can return confidence, audio evidence, and provider-authored correction guidance. Voice identity, raw pitch similarity, and generic TTS are not evaluation signals.
- The lesson unlock rule is an exact recognized-word match of at least 90% against the reviewed, selected-profile reference sequence, with approved Guru reference audio present. Pronunciation scoring and voice identity are not part of this unlock rule.
- Unavailable or low-evidence results never unlock a lesson.

## Current capability

Suśrotā Sanskrit ASR and a Vedic Wav2Vec2 CTC forced aligner are now available as **opt-in local providers**. ASR, known-text alignment, pronunciation assessment, and svara now have separate provider interfaces and configuration (`EVALUATION_ENGINE`, `ALIGNMENT_ENGINE`, `PRONUNCIATION_ENGINE`, and `SVARA_ENGINE`). The defaults remain disabled (`EVALUATION_ENGINE=none`, `ALIGNMENT_ENGINE=none`, `PRONUNCIATION_ENGINE=none`, `SANSKRIT_ASR_ENABLED=false`, `PRONUNCIATION_EVALUATION_ENABLED=false`). Both models load from local files only; the app does not download model weights at runtime. If model files or configuration are absent, the providers fail closed. `scripted` remains fixture-only and is not acoustic evidence.

The Suśrotā provider returns a Sanskrit transcript candidate. Its ASR output is not a pronunciation score. The independent aligner accepts the known Sanskrit target and returns candidate word and orthographic akṣara timestamps plus uncalibrated CTC frame posteriors. A forced fit can assign timestamps to incorrect text; these timestamps are not verified against human boundaries. When an evaluation includes these timestamps, the Flutter lesson screen can replay the learner's aligned word or akṣara segment; it offers Guru word playback only when a Guru clip or reviewed timing is available. The models were smoke-tested against all nine mapped Guru clips, but these are reference samples, not student attempts.

When a local known-text aligner is enabled and Guru audio is present, the pipeline now runs that same aligner independently on both the learner and Guru recordings. It reports normalized word duration and pause differences in `guru_student_timing_comparison` and displays them in the lesson screens as a preview. Normalizing by each clip duration removes overall speaking-speed differences; the per-word relative timing is still only a diagnostic. This feature cannot detect phoneme errors, and the result has no pronunciation score or pass/fail outcome.

The nine published lesson strings and generated Suśrotā transcripts remain pending Guru review. The supplied Padapāṭha data still lacks an available, reviewed source segmentation. The recording and learning APIs now accept a separate `Common` profile in addition to Kanchi/Sringeri; it has an independent namespace and does not fall back to either tradition. There are no reviewed Common records yet, so requests continue to return unavailable until Common text and reference audio have been reviewed and rights-cleared.

For local smoke testing only, set `APP_ENV=development` and `EVALUATION_TEST_MODE=true`. This diagnostic compares ASR with the full lesson text as an **unreviewed candidate**, and loads the matching bundled Guru clip under `mobile/assets/audio/guru_reference`. The Compose API and worker mount those clips read-only. It reports candidate forced alignment and timing previews as well. Reports are labeled diagnostic-only and are always rejected for progress/unlock; this mode is never enabled by the production example configuration. It does not assess pronunciation. The nine-clip ASR benchmark above shows substantial word segmentation/transcript mismatch, so a lower candidate word match should be expected until the text/audio mapping is reviewed.

The backend now has a replaceable, provisional Sanskrit orthographic G2P mapper in `backend/app/services/sanskrit_g2p.py`. It represents expected vowels, consonants, aspiration/place distinctions, anusvāra/visarga, and akṣara grouping; unresolved avagraha is explicitly flagged. It is text-derived reference data only, not audio evidence, and every result is marked ineligible for evaluation until Guru review. The current nine-lesson candidate export is `content/Evaluation_G2P_candidates.json` (75 words); its source text and phoneme hypotheses remain pending review. It has unit tests for minimal contrasts and known edge cases but is not a complete scholarly grammar or dialect model.

`backend/poc/validate_evaluation_bundle.py` checks a returned review package before a human-evaluation run: approval and rights fields, Common profile, consent, label/sample association, timestamps within each audio duration, audio presence, and SHA-256 inventory. It rejects unsafe audio paths and possible personal identifiers in learner sample rows. It does not import records, infer pronunciation, or report model accuracy. Example (from the repository root):

```powershell
python backend/poc/validate_evaluation_bundle.py `
  --guru-csv content/Evaluation_guru_word_review_template.csv `
  --samples-csv content/Evaluation_learner_samples_template.csv `
  --labels-csv content/Evaluation_learner_labels_template.csv `
  --guru-audio-dir mobile/assets/audio/guru_reference `
  --learner-audio-dir path/to/consented_learner_audio `
  --output content/Evaluation_bundle_validation.json
```

The current templates intentionally fail readiness because their reviews are pending and learner consented audio/labels have not been supplied. A passing validator is only a prerequisite for acoustic benchmarking; it is not evidence of benchmark quality or permission to enable production pronunciation scores.

For an offline held-out comparison, `backend/poc/score_pronunciation_benchmark.py` joins provider predictions to reviewed events by unique `event_id`. It reports coverage/abstention, false-positive and false-negative counts, precision/recall/specificity/F1 by issue category, and start/end timing MAE where available. A missing event prediction is counted as an abstention. The report always sets `score_enabled` to false; production scoring remains gated on reviewed data, calibrated acoustic evidence, and independent acceptance review.

No validated Sanskrit phoneme posterior/GOP model, acoustic phonetic assessor, calibration dataset, or Vedic svara engine is available. The Suśrotā project documents an earlier GOP forced-alignment experiment with strong offline AUC, but says it was too false-positive-prone for a tutor and was superseded by decode-consensus, text verification, and abstention. That reinforces the need to calibrate against this application's own Guru-labelled attempts before surfacing pronunciation errors. Phoneme-level error labels, vowel-length and consonant articulation scoring, Guru/student acoustic comparison, and Vedic svara scores are therefore intentionally unavailable. ASR transcripts and forced-alignment evidence do not satisfy those requirements.

## Nine-lesson Evaluation reference set

`content/Evaluation.json` contains the ordered Devanāgarī word tokens from the current published texts for `rigveda-01` through `rigveda-09`, mapped to their supplied Guru audio assets and SHA-256 fingerprints. The nine source audio files were checked against the mapping manifest. The `reference_words` are copied from the lesson text and split on whitespace; they are **not** transcriptions produced by listening to or recognizing the Guru recordings. Each row remains `pending_sushrota_inference_and_guru_review` until the actual audio transcript and any sandhi/word-boundary differences are checked. Do not enable these rows as an ASR result or pronunciation score by themselves.

The app can compare a recognized transcript with ordered reference tokens through the existing pipeline when the appropriate reviewed profile record is available and a provider is enabled. ASR transcript agreement alone does not establish vowel length, consonant articulation, pronunciation quality, or Vedic svara.

## Model benchmark (CPU, nine Guru clips)

The production candidate is the Apache-2.0 ONNX export of Suśrotā, based on the upstream IndicConformer-CTC work. The forced aligner card declares Apache-2.0 and exposes CTC character logits for known-text alignment. Sanskrit Whisper's model card declares Apache-2.0; it was screened and rejected on this corpus. See the [Suśrotā ONNX model card](https://huggingface.co/gnumanth/sushrota-sanskrit-asr-onnx), [Suśrotā upstream model](https://huggingface.co/prathoshap/sushrota-sanskrit-asr), [Vedic aligner model card](https://huggingface.co/chiranjeevisagi/wav2vec2-vedic-aligner), and [Sanskrit Whisper model card](https://huggingface.co/rverma251/sanskrit-whisper-asr) for the source model documentation and license terms. The application uses the local ONNX files; it does not fetch model code or weights at runtime.

The local Suśrotā ONNX INT8 model was run through the production provider against the nine exact mapped OGG files. It returned a transcript on all 9; mean character error rate against the current lesson text was 7.41%, and whitespace word error rate was 74.32%. The text is not Guru-verified, and whitespace WER is especially sensitive to Sanskrit sandhi and segmentation. These are ASR corpus-screening metrics only, not pronunciation accuracy.

The Vedic Wav2Vec2 ONNX INT8 aligner produced candidate word and orthographic-akṣara timestamps for all 9 recordings (9/9 and 9/9). There are no human timestamp labels, so alignment accuracy cannot be calculated. No pronunciation scores were produced. The forced-alignment run is a compatibility smoke test, not proof the source text matches each Guru recording.

Sanskrit Whisper was screened as an independent transcript candidate and rejected for this set: mean CER 133.87%, whitespace WER 198.46%, and mean CPU inference 17.30 seconds per clip. Its output was repetitive/garbled. It is not registered as a production provider.

Detailed reports: `content/Evaluation_ASR_candidates_verified.json`, `content/Evaluation_Vedic_aligner_candidates.json`, `content/Evaluation_Sanskrit_whisper_candidates.json`. Local reproducible smoke runner: `backend/poc/production_engine_smoke.py`.

## Implementation gates still open

1. Guru review the nine expected text/transcript mappings and confirm their audio-to-shloka associations.
2. Guru review and add Common profile text and reference audio; do not mix those records with Kanchi or Sringeri.
3. Supply Guru-labelled learner examples and time/phoneme annotations for evaluation. The Guru recordings alone cannot measure learner pronunciation false positives or false negatives.
4. Have a Sanskrit reviewer validate the provisional G2P inventory against the Common recitation and define variant/sandhi handling; select or train a phonetic acoustic model that exposes calibrated evidence for that same inventory.
5. Then implement and validate acoustic comparisons, scores, feedback UI, and history. Do not enable score/unlock behavior from ASR similarity or forced-fit posteriors.

IndicMFA was also screened. Its Sanskrit release is a graph-to-graph MFA aligner with a grapheme-as-pronunciation dictionary; it targets letter alignment, not the Sanskrit phoneme distinctions and calibrated pronunciation likelihoods needed here. The project does not declare a license on its repository page, so its model assets are not integrated.

## Profile text administration

`POST /api/recitation/admin/profile-text` stores the original Saṃhitā form, source Padapāṭha form, ordered source word tokens, phonetic metadata, and provenance in a pending state. `POST /api/recitation/admin/profile-text/{id}/review` records validation and rights decisions. Tokens require contiguous order and verbatim source forms; provenance requires a title, locator, and SHA-256. Only `validated` and rights-cleared/public-domain rows are used by evaluations. Run migrations `0012`–`0014` before enabling the complete learning flow.
