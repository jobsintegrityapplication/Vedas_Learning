# Evaluation data review guide

These templates collect the human evidence needed to validate the Sanskrit evaluation pipeline. The nine Guru OGG files and source-word rows are already mapped in `Evaluation_guru_word_review_template.csv`; source words are suggestions only until a Guru approves them.

## Guru transcript and timing review

For each row in `Evaluation_guru_word_review_template.csv`:

- Confirm or replace `guru_approved_word` against the supplied recording. Preserve Sandhi and the Guru's actual recitation convention.
- Enter `start_ms` and `end_ms` for that spoken word, measured from the start of the corresponding source audio. Boundaries must satisfy `0 <= start_ms < end_ms`.
- Set the text and timing review statuses to `approved` only after listening and checking the row. Otherwise keep `pending` or use `rejected` and explain in `notes`.
- Confirm the `Common` profile and `rights_status` for each audio/text record; use `cleared` or `public_domain` only when the owner has confirmed that status.
- Add reviewer identity and any notes about recitation variation. The application will not treat the ASR candidate as authoritative.

## Student sample register

Add one row per recording to `Evaluation_learner_samples_template.csv`. Use an anonymous `speaker_code`, identify the matching lesson, and set `consent_status` to `confirmed` only when the speaker has agreed to use the recording for evaluation development. Enter a human-checked transcript and mark its review status. Do not include names, email addresses, phone numbers, or other identifying details.

## Student error labels

Add one row per reviewed word/error event to `Evaluation_learner_labels_template.csv`:

- Assign each row a unique `event_id`; it is the stable key used to compare a model finding with the human judgment. Create separate rows for separate sound targets/events, even when they occur in the same word.
- `expected_word` is the reviewed Guru target; `observed_word` is what the reviewer hears. Leave blank when the word is omitted or cannot be determined.
- `issue_category` can be `correct`, `omission`, `substitution`, `insertion`, `repetition`, `vowel_length`, `vowel_quality`, `dental_retroflex`, `aspiration`, `voicing`, `sibilant`, `anusvara_visarga`, `conjunct`, `rhythm`, `svara`, or `unclear`.
- For feature-level negative examples, keep the feature in `issue_category` (for example, `vowel_length`) and set `label` to `correct`. The label says whether the target feature was pronounced correctly; the category says what feature the event evaluates. Use category `correct` for an overall word-level correct event.
- For a phonetic issue, fill `expected_phonetic_feature` and `observed_phonetic_feature` with the specific sound/feature, not a free-form score.
- Add `start_ms`/`end_ms` for the issue in the student recording. Mark `label` as `correct`, `incorrect`, or `uncertain`; add reviewer confidence and notes.
- Use `unclear`/`uncertain` when the audio does not support a reliable judgment. Those cases must not become false error labels.
- Include determinate correct and incorrect examples for every sound category being evaluated. Errors alone cannot reveal false positives; uncertain rows are excluded from accuracy metrics.

For held-out scorer results, export JSON with `provider_id`, `provider_version`, and an `events` array. Each event needs `event_id`, `predicted_label` (`correct`, `incorrect`, or `uncertain`), and `confidence` from 0 to 1; `start_ms`/`end_ms` are optional. Run `backend/poc/score_pronunciation_benchmark.py` to calculate event coverage, false-positive/false-negative counts, precision/recall/specificity/F1 per feature, and timestamp mean absolute error when both sides have boundaries. Missing predictions count as abstentions. This report is offline evidence only and cannot enable production scoring.

Transcript text by itself is not a pronunciation label. A learner example needs a reviewed sound-level event before it can validate vowel, consonant, phoneme, or svara assessment. Keep learner audio separate from Guru reference audio and do not use ASR-generated timestamps as human labels.

## Files to return

Upload the completed Guru review CSV, the learner sample register, the learner error-label CSV, and the consented audio files whose filenames appear in the register. Include any corrected Guru transcripts and timings. I will validate the references, run the samples through the providers, compare against the human labels, and report the false-positive/false-negative and per-feature results before enabling score-based feedback.
