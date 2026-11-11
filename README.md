# Vedas Learning

See [ARCHITECTURE.md](ARCHITECTURE.md) for the repository layout and MVC responsibility map.

Production-oriented learning platform for Guru-approved Vedic recitation practice on Android, iOS and Web.

## What is implemented

- Registration, email OTP, login and password reset (JWT)
- Learner profile (name, date of birth, gender, phone, email, Rashi, Nakshatra, profession)
- Admin-only customer overview with aggregate account, recent sign-in, age-band, gender and profession counts; it does not expose individual customer contact details
- Learner activity history: foreground app sessions, lesson study time, lesson completion, course completion periods, audio interactions, recording submissions, and sign-in events
- Scripture catalog for the four Vedas, Ramayana, Mahabharata and Bhagavad Gita
- Nine source-document Rigveda lessons seeded from `content/rigveda_lessons.json` and tracked for Guru review in the review manifest
- Lesson text, optional transliteration, word meanings and Guru reference audio (when uploaded)
- Line-indexed recitation workflow with private recording uploads, retries, persisted learner self-marked line history and sequential unlocking
- Interface language selector for English, Hindi, Kannada, Tamil, Telugu, Malayalam, Marathi, Bengali, Gujarati and Punjabi
- Rigveda content/audio review manifest at `content/rigveda_review_manifest.json`; candidate audio stays unverified and noncanonical pending Guru and license review
- Learner recording upload to S3-compatible storage
- Background evaluation worker (Celery) with **honest capability reporting**
- Progress dashboard and admin APIs for scriptures, lessons and reference audio
- PostgreSQL, Redis, MinIO, Mailhog via Docker Compose

## Critical content rule

Guru-approved Sanskrit, meanings and reference audio are the source of truth. Seed inserts missing lessons only and **never overwrites** existing verse text. Admin updates that change Sanskrit or meaning require `confirm_guru_edit=true` and are audited. The application does not invent verses, transliteration or word meanings.

## Evaluation status

Word accuracy, pronunciation and Vedic svara are separate capabilities.

| Capability | Status |
| --- | --- |
| Store learner audio | Implemented |
| Token alignment **when a transcript exists** | Implemented and tested as a pure function |
| Sanskrit ASR / forced alignment against Guru audio | **Not configured** |
| Pronunciation / phoneme scoring | **Not configured** |
| Vedic svara | **Not configured** (no specialist engine) |

The API does not compare speaker identity, voice similarity or pitch as a proxy for correctness, and it does not fabricate scores.

## Rigveda source and review status

`content/rigveda_lessons.json` is imported without overwriting existing database text. `content/rigveda_review_manifest.json` records the nine supplied references, issues for Guru review, recording source metadata, license status and verification status. The source DOCX remains the wording authority; do not silently complete excerpts or edit meaning/Sanskrit. In particular, lesson 6 text is from Rigveda 10.191.3 while its supplied reference says 10.191.4; lesson 1 meaning maps ऋतेन to “By Yagna”; lessons 2, 4, 5, 7 and 8 are partial verse excerpts. Guru review is required before changing these.

The current audio manifest contains Vedic Heritage Portal full-sukta candidates and two YouTube candidates. Candidate recordings are not canonical, are not played from the manifest, and are not copied into the app. The portal pages do not state a reuse license; treat them as link-only until rights and Guru approval are documented. Admin-uploaded private reference audio is the only audio asset exposed in the learner flow. Upload only Guru-approved material.

Line completion currently uses explicit learner self-attestation, not an accuracy gate. Sanskrit audio references have not been timed to each line; playback, repeat and slow speed operate on the uploaded reference asset. Word omission/substitution feedback is available only when a configured transcription engine returns token evidence. This repository has no validated Sanskrit ASR, phoneme, vowel-duration or svara engine, so those results remain unavailable. IAST and pronunciation guidance are not present in the source and must be reviewed before publication. The ten locale labels are provisional interface copy; professional translations of meanings, applications and feedback remain pending review and approval.

Approved lesson translation entries use `Lesson.translations` JSON by locale code, for example `{"hi":{"status":"approved","meaning":"...","daily_application":"..."}}`. The learner client displays lesson meaning/application translations only when the locale entry has `status: approved`; otherwise it retains the source language copy and shows a review notice. Admin changes continue through the existing audited lesson CMS.

### Supplied Mandala PDF ingestion

The ten Kanchi-labeled and ten Sringeri-labeled PDFs are source candidates only. Install the script dependency with `python -m pip install -r scripts/requirements-ingestion.txt`, then run `python scripts/ingest_rigveda_pdfs.py --kanchi-dir <path> --sringeri-dir <path>` to create page and heuristic mantra-candidate JSONL/CSV files plus a PostgreSQL staging import script under `content/ingestion/`. The script preserves each embedded source string and page, applies NFC only in a separate field, records SHA-256/method/confidence, preserves non-black RCCS glyph color and position cues, and flags unreliable text layers. OCR fallback is page-selective and requires Poppler plus Tesseract trained with `hin` and `eng`; without those tools affected pages remain flagged, not repaired. RCCS is retained as source notation; the IAST field is only an unconverted candidate and is not certified as IAST. Candidate references and segmentation require review and must not be treated as canonical corpus text.

To compare source address coverage and keep profile-specific text separate, run `python scripts/reconcile_rigveda_profiles.py`. This writes provisional identity and variant JSONL/CSV datasets, `reconciliation_report.md`/`.json`, `source_coverage_dashboard.html`, and PostgreSQL schema/import files under `content/reconciliation/`. It checks per-Maṇḍala Sūkta/mantra totals against the documented Śākala structure. If a candidate page has uncertain extraction, the variant remains publication-blocked; the current run blocks all records because OCR was unavailable for every page.

To create Padapāṭha records, run `python scripts/build_padapatha_records.py`. It stores the original Saṃhitā form, ordered Padapāṭha tokens, transliteration, phonetic features, vowel length, Vedic accent, sandhi links, and provenance as separate fields. It never splits Saṃhitā text by whitespace or infers sandhi reversal. The supplied PDFs do not provide verified Padapāṭha, so all 14,260 current profile-variant records are marked unavailable and publication is blocked. When source-attested Padapāṭha becomes available, supply the documented JSONL contract in `content/padapatha/README.md` using `--padapatha-source`; uncertain or unreviewed segmentation remains blocked.

Kanchi and Sringeri reference audio now use independent profile/address records. Full-mantra and timestamped word clips retain source and speaker attribution, URLs, rights, validation state, and checksums; playback exposes only validated assets with cleared rights. Learner uploads carry a profile and are stored in separate namespaces. No chanting is synthesized, and absent audio is reported unavailable. See `content/RECITATION_AUDIO.md` for endpoint and review details. Apply the `0012` Alembic migration before using these endpoints.

Speech evaluation is profile-keyed and fail-closed: it requires an approved, rights-cleared profile Padapāṭha word sequence and never falls back to another tradition. Transcription token alignment reports word omissions/substitutions; a configured provider may additionally return validated word timestamps and acoustic evidence for vowel length, consonants, aspiration, visarga, anusvāra, and Vedic accent. This repository has no production Sanskrit ASR, forced aligner, phoneme analyzer, or svara engine configured, and no current Padapāṭha/audio profile rows are available; speech and feature assessment therefore remain unavailable until source data and a validated provider are supplied. See `content/SPEECH_EVALUATION.md`; apply Alembic migration `0013` for profile text references.

The progressive mantra library integrates Maṇḍala → Sūkta → mantra navigation, profile-specific source-preserving Sanskrit reading, word listening/recording/evaluation/retry, gated unlocks, combined and full-mantra recitation, persisted reports, per-profile progress dashboards, bookmarks and resume. Progressive interface copy supports English, Hindi, Kannada, Tamil, Telugu, Malayalam, Marathi, Bengali, Gujarati and Punjabi. It lists only reviewed, rights-cleared records; currently it will show the explicit empty/unavailable state because none of the imported candidates is approved yet. See `content/PROGRESSIVE_LEARNING.md` and apply migration `0014` after `0012` and `0013`.

## Local deployment

On Windows, double-click `run-veda-learning.bat`. It starts Docker Desktop if available, builds and runs the API, database, worker, local mail inbox and Flutter web app, waits for readiness, then opens the app and MailHog. Use `stop-veda-learning.bat` to stop the containers; persistent data volumes are kept.

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for production Compose, secrets, Android Play release, and iOS App Store steps (macOS/Xcode required). Never commit `.env` or keystores.

```bash
cd veda_learning_poc
cp .env.example .env
docker compose up --build -d
```

- API health: http://127.0.0.1:8000/health
- API ready: http://127.0.0.1:8000/ready
- Docs (local only): http://127.0.0.1:8000/docs
- Mailhog: http://127.0.0.1:8025
- S3-compatible storage: http://127.0.0.1:9000

If those host ports are already in use, set `HOST_API_PORT`, `HOST_DB_PORT`, `HOST_REDIS_PORT`, and `HOST_S3_PORT` in `.env`.

Default admin is in `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). Change it before any shared environment.

Backend tests:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```

## Flutter (Android, iOS, Web)

```bash
cd mobile
flutter pub get
flutter run                 # attached device or emulator
flutter run -d chrome       # web
```

API host: Android emulator `http://10.0.2.2:8000`; iOS/web/desktop `http://127.0.0.1:8000`. Override with `--dart-define=API_BASE_URL=https://your-api`.

## Remaining production work

- Validated Sanskrit ASR / forced alignment and phoneme scoring against Guru reference audio
- Validated Vedic svara engine, if one is approved
- Real SMTP credentials, HTTPS, secret rotation, backups and observability in the target environment
