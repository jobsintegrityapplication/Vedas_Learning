# Vedas Learning — Implementation Plan

**Audit date:** 5 November 2026  
**Scope:** `veda_learning_poc` frontend (Flutter), backend (FastAPI), database (SQLAlchemy/Alembic), Docker, dependencies, architecture, tests.  
**Constraint:** Do not rewrite working code. This document is the backlog only; no implementation starts from this audit.

---

## 1. Current architecture (what exists)

```
Flutter (Android / iOS / Web)
    -> FastAPI (JWT)
        -> PostgreSQL
        -> Redis + Celery worker
        -> MinIO (S3-compatible)
        -> SMTP (Mailhog locally)
Guru text seed: content/rigveda_lessons.json (insert-if-absent)
```

**Working and should be preserved**

- Registration, OTP verify, login, password reset (bcrypt, hashed OTP, JWT access tokens)
- Learner profile fields (name, age, phone, email, Rashi, Nakshatra, profession)
- Scripture catalog (seven titles) and nine Guru-provided Rigveda lessons from the JSON source
- Seed refuses to overwrite existing Sanskrit/meaning
- Admin API requires `confirm_guru_edit` to change Sanskrit/meaning and writes `lesson_audits`
- Recording upload path (auth required) and honest evaluation statuses (`unavailable` / `not_configured`)
- Token alignment as a pure function (not used as a fake audio score)
- Progress API (`/api/progress/me`)
- Alembic `0001_initial`, Docker Compose file, pytest (8 passing), one Flutter widget test
- Android mic/internet permissions; iOS `NSMicrophoneUsageDescription`

This is a solid skeleton, not a complete production system.

---

## 2. Product gaps (features specified but missing or incomplete)

| Requirement | Status |
| --- | --- |
| Android / iOS / Web clients | Scaffolded; Web and iOS not production-hardened |
| Email OTP in production | Dev-only: OTP returned in JSON; SMTP failures swallowed in `is_dev` |
| Password reset | API exists; Flutter UI exists; no rate-limit per email, no session revoke after reset |
| Chapter management | DB table + admin create only; learners never see chapters |
| Transliteration, word meanings | Schema exists; source JSON has none; UI shows only if API sends them — do **not** auto-generate |
| Guru reference audio | Upload API exists; admin Flutter screen cannot upload; no public playback host mapping |
| Compare recitation vs Guru audio | **Not implemented.** Worker always calls evaluation with `hypothesis_tokens=None` |
| Skipped / substituted / incorrect words from audio | Alignment code exists; never fed a real ASR/forced-alignment transcript |
| Pronunciation evaluation | Explicitly unavailable — correct; no engine plug-in interface yet |
| Vedic svara | Explicitly unavailable — correct; must stay unavailable until a specialist engine is approved |
| Progress dashboards | Minimal counts + history list; no charts, streaks, per-scripture breakdown, or admin analytics |
| Admin panel | API-only CRUD subset; Flutter admin is a read-only lesson list |
| Content for Yajurveda, Samaveda, Atharvaveda, Ramayana, Mahabharata, Gita | Catalog rows only; no Guru lessons (correct until Guru provides them) |

---

## 3. Security findings

### P0 — fix before any non-local deployment

1. **Default secrets.** `SECRET_KEY`, `ADMIN_PASSWORD`, MinIO keys, Postgres password are weak defaults in `.env.example` and `config.py`. Compose publishes Postgres `5432`, Redis `6379`, MinIO `9000/9001` to the host with those defaults.
2. **`demo_otp` in API responses** whenever `APP_ENV` is `development`/`dev`/`local`/`test`. Easy to ship to staging if env is mis-set.
3. **JWT refresh tokens are issued and unused.** No `/api/auth/refresh`, no rotation, no revocation, no server-side store. Stolen refresh tokens cannot be invalidated. Access tokens live only in Flutter memory (also a UX gap).
4. **No upload size limit** on learner or Guru audio (`await audio.read()` loads the whole body). Enables disk/memory exhaustion.
5. **CORS:** `allow_credentials=True` with `allow_origins` falling back to empty-list-or-`["*"]` in `main.py`. Credentials + wildcard is invalid/dangerous if origins misconfigured.
6. **Auth rate limits are too weak.** Global SlowAPI `60/minute` per IP; login/register/OTP are not tighter. Credential stuffing and OTP brute force remain practical (`otp_max_attempts` is per stored row, not per IP).
7. **Profile email is writable independently of `users.email`.** Learners can store a different email on the profile without verification.
8. **Admin bootstrap password never rotated** after first seed; changing `ADMIN_PASSWORD` in env does not update the DB user.

### P1 — security hardening

9. **Presigned MinIO URLs** use `S3_ENDPOINT_URL=http://minio:9000`. Mobile/web cannot play Guru audio unless a public endpoint (`localhost:9000` or a gateway) is used for signing.
10. **Cleartext HTTP.** Android `usesCleartextTraffic=true` is unconditional. iOS has no ATS exception/documentation. Web talks to `http://127.0.0.1:8000`.
11. **No HTTPS, HSTS, or reverse proxy** in Compose.
12. **Email enumeration** on register (`409 Email already registered`) vs generic forgot-password. Acceptable for some products; tighten if privacy requires it.
13. **OTP hashed with bcrypt (cost 12).** Safe but slow; fine. Codes are 6-digit numeric (1e6 space) — needs strict rate limits (see P0.6).
14. **No audit of admin authentication events**, no 2FA for admin.
15. **Health check hits the database** and is unauthenticated (DoS/info). Split liveness vs readiness.
16. **Filename from client** is sanitized only by basename; still stored in DB (`original_filename`) without content-type sniffing.
17. **No retention/consent policy** for learner recordings (privacy).
18. **Token not in secure storage** on device; logout does not hit the server.

---

## 4. Duplicate, dead, and inconsistent code

Do not mass-refactor; remove or wire only what is listed.

| Item | Issue |
| --- | --- |
| `mobile/lib/api.dart` | **Dead duplicate** of `ApiClient`. Uses `dart:io` (breaks Web if imported), old `user_id` form field the backend no longer accepts. Unused by `main.dart`. |
| `AUDIO_EXT` vs `ALLOWED` | Same extension set copied in `admin.py` and `recordings.py`. |
| `JSONType` | Duplicated in `models/content.py` and `models/learning.py`. |
| `GURU_FIELDS` | Declared in `content_integrity.py`, never used. Fingerprint covers only Sanskrit + meaning. |
| Admin `Form` import | Unused import in `admin.py`. |
| Flutter `Session.refresh_token` | Backend returns `refresh_token`; client ignores it. |
| Profile controllers | Never disposed; profile is not pre-filled from `GET /api/profile`. |
| `httpx` in requirements | Unused by application code. |
| README vs `pubspec` | README claims production platform; pubspec still says “starter”. |

---

## 5. Broken or incomplete implementations

1. **Evaluation pipeline is a stub by design, but the worker reports `status: completed`.** Product-wise this looks like “evaluation finished” while word/pronunciation/svara remain `unavailable`. Clients may treat `completed` as success. Prefer `status: unavailable` / `not_configured` unless an engine actually ran.
2. **Celery fallback** (`delay` except then run inline) hides broker outages and can block the API on bcrypt-unrelated work.
3. **Guru audio playback** will fail on devices: presign host is the Docker-internal hostname.
4. **Web recording** uses a relative filename path; untested on Chrome. Widget tests do not cover recording.
5. **No JWT refresh path** — after 60 minutes the user is stuck until login.
6. **Chapters:** unique `(scripture_id, sort_order)` will collide if two chapters share order; no learner list endpoint.
7. **Admin Flutter** cannot create/edit lessons, confirm Guru edits, or upload reference audio — contradicts “admin panel” requirement.
8. **Tests use SQLite**, not PostgreSQL. UUID/timezone behavior already differed (naive vs aware datetimes). CI will not catch PG-only bugs.
9. **Compose `minio:latest` / `mailhog:latest`** unpinned; `minio-init` uses `sleep 3` instead of a healthcheck (flaky first boot).
10. **API image command** runs migrate + seed on every start; seed is insert-only (good) but admin password seed is insert-only (stale password, see security).
11. **Flutter Web** `index.html` is the stock template (“A new Flutter project”), no mic permission UX.
12. **No CI workflow.**

---

## 6. Test gaps

Covered today: alignment skip/substitute/extra, honest unavailable evaluation, register/verify/login/profile, password reset, seed immutability, welcome widget.

Missing:

- Admin authz (learner 403, admin 200)
- `confirm_guru_edit` rejection and audit row
- Recording upload (size, type, auth)
- Evaluation worker persistence of `unavailable` vs `completed`
- JWT expiry / wrong type / missing bearer
- OTP expiry, max attempts, consumed OTP
- Postgres integration (Docker) for migrations
- Flutter: login error, lesson list from mock client, accessibility
- No load/security tests

---

## 7. Prioritized tasks

### P0 — correctness and safety (do first)

| ID | Task | Notes |
| --- | --- | --- |
| P0-1 | Fail fast if `SECRET_KEY` / admin password / DB password are defaults when `APP_ENV` is not local | Keep local DX |
| P0-2 | Stop returning `demo_otp` unless an explicit `EXPOSE_DEV_OTP=true` flag is set | Do not rely on `is_dev` alone |
| P0-3 | Cap audio upload size; reject empty/oversize before S3 | Learner + admin |
| P0-4 | Tighten rate limits on register, login, verify, forgot, reset | Per IP and per email |
| P0-5 | Fix evaluation record `status` so “no engine” is not `completed` | Contract for the Flutter result card |
| P0-6 | Bind MinIO presign to a browser-reachable URL (`S3_PUBLIC_ENDPOINT_URL`) | Required for Guru playback |
| P0-7 | Delete or quarantine dead `mobile/lib/api.dart` | Prevent accidental Web import |
| P0-8 | Persist session (secure storage) **or** document that restart logs the user out | Prefer secure storage + refresh endpoint |
| P0-9 | Add PostgreSQL pytest job (Compose) for auth + seed immutability | SQLite is not the production dialect |
| P0-10 | Do not expose Postgres/Redis/MinIO on `0.0.0.0` in any non-dev overlay | Compose ports are fine for local-only |

### P1 — product completeness (no fake evaluation)

| ID | Task | Notes |
| --- | --- | --- |
| P1-1 | Implement `/api/auth/refresh` with rotation; store refresh hashes; revoke on reset/logout | Client must send refresh |
| P1-2 | Learner chapter list + lesson-by-chapter; admin update/delete chapter | Empty chapters until Guru content exists |
| P1-3 | Admin Flutter: lesson metadata, reference-audio upload, confirmed Guru text edit with note | Never auto-edit Sanskrit |
| P1-4 | Wire Guru audio player to public presigned URL; empty state already exists | |
| P1-5 | Profile: GET prefill, dispose controllers, keep profile email equal to verified `users.email` | |
| P1-6 | Progress dashboard: per-scripture counts, last practice, no invented scores | |
| P1-7 | Production SMTP path: fail closed when email cannot send (non-dev) | Already raises outside `is_dev`; add retries/metrics |
| P1-8 | iOS ATS / Android cleartext only for debug; HTTPS in release | |
| P1-9 | Upload tests + admin authorization tests | |
| P1-10 | Pin Docker image tags; healthcheck MinIO before `mc mb` | |

### P2 — evaluation engine (only with Guru audio + validated model)

| ID | Task | Notes |
| --- | --- | --- |
| P2-1 | Define an `EvaluationEngine` interface: input = (Guru audio, Guru tokens, learner audio); output = hypothesis tokens + optional phoneme scores | No speaker-ID, no pitch-as-correctness |
| P2-2 | Forced alignment / Sanskrit ASR **after** Guru reference audio exists per lesson | Skip lessons without Guru audio |
| P2-3 | Map hypothesis tokens through existing `align_tokens` for skipped/substituted/extra | Reuse, do not duplicate |
| P2-4 | Pronunciation scores only from a documented acoustic/phoneme method | |
| P2-5 | Svara remains `unavailable` until a named, validated specialist engine is approved | Do not ship a placeholder |
| P2-6 | UI: three separate capability cards (word / pronunciation / svara) with reasons | |

### P3 — polish, ops, accessibility

| ID | Task | Notes |
| --- | --- | --- |
| P3-1 | go_router, Semantics labels, text scaling, Web mic prompt | |
| P3-2 | Recording retention, export, and delete-my-data | |
| P3-3 | Structured request IDs, metrics, log redaction of emails/OTP | |
| P3-4 | CI: pytest + `flutter analyze` + `flutter test` | |
| P3-5 | Deduplicate audio extension sets and JSON type helper (small, isolated) | |
| P3-6 | Pin Python/Flutter dependency upper bounds for reproducible builds | Current backend pins are loose `>=` |
| P3-7 | Admin 2FA, scripture update/unpublish, lesson unpublish | |
| P3-8 | Ingest additional Guru-approved corpora when provided — never invent | |

---

## 8. Risks

- **Content integrity:** Any “helpful” transliteration/NLP fill-in would violate the Guru source-of-truth rule.
- **Evaluation credibility:** Shipping numeric scores without a validated engine would be a product defect, not a missing feature.
- **SQLite tests vs Postgres:** False confidence; timezone and UUID already diverged once.
- **Celery + MinIO first-boot:** Compose will look “up” while audio upload returns 503 if bucket init races.
- **Existing emulator session** may still run the pre-JWT APK against a new API (auth mismatch).

---

## 9. Explicit non-goals until unblocked

- Do not generate Sanskrit, meanings, transliteration, or word lists.
- Do not compare voices or pitch as correctness.
- Do not mark svara complete.
- Do not rewrite the working auth/profile/seed/alignment modules as a “cleanup.”
- Do not fill empty scriptures with sample verses.

**Unblockers for P2:** Guru-approved reference recordings stored via admin upload; written evaluation protocol from a Sanskrit/Vedic specialist; engine version recorded on every `evaluations` row.

---

## 10. Corpus scope: complete Ṛgveda Śākala Saṃhitā

The planned canonical corpus is the complete Śākala Saṃhitā: 10 Maṇḍalas, 85 Anuvākas, 1,028 Sūktas and approximately 10,552 mantras/ṛcs, including the conventionally included Vālakhilya hymns. This is the target scope, not a statement of current data coverage. The repository currently contains nine learning excerpts. See [CORPUS_SPEC.md](CORPUS_SPEC.md) and [SOURCE_REGISTER.md](SOURCE_REGISTER.md).

### Work sequence / release gates

1. **Source and rights gate:** select a specific complete edition and text form (Samhitā, Padapāṭha, or separately versioned both); record edition, provenance, URL/citation, retrieval date, license/permission and source-file SHA-256. Resolve redistribution rights before copying text/audio into the product.
2. **Profile gate:** establish separate Kanchi and Sringeri recitation profiles. Obtain profile-specific teacher/performer provenance, recording source, rights, text edition/alignment and Guru review. Do not infer differences or create recordings from profile names.
3. **Data model and ingestion:** add versioned corpus/source/edition records and stable mantra addresses; ingest source-backed units without overwriting approved content. Store accent/pāda details and source locator. Quarantine omissions, conflicts, and unlicensed material; never generate missing content.
4. **Coverage reconciliation:** compare all imported units with the selected edition's sukta/mantra inventory; report missing, duplicate, and disputed addresses. Claim completeness only after reconciliation and qualified review sign-off.
5. **Learning experience:** navigate Maṇḍala → Sukta → mantra, expose source/edition and profile selection, and show honest unavailable states for absent or unapproved audio. Keep Kanchi and Sringeri assets independent.
6. **Operational review:** preserve import manifests, transformation history, checksums, rights evidence, and reviewer approvals. Recompute checksums after changes and record each corpus release/version.

**Available source candidates and reconciliation:** the user supplied ten Kanchi-labeled and ten Sringeri-labeled Mandala PDFs. Their metadata identifies SaiVeda / `www.saiveda.net` but not a dated edition. Ingestion wrote 4,130 page records and 21,191 heuristic candidates. Reconciliation created separate identity and variant datasets: 6,963 provisional shared addresses, 98 profile-only candidate addresses, 233 duplicate-address groups, and zero measured order conflicts among common explicit candidates. No textual differences were adjudicated because all 4,130 pages are flagged for uncertain extraction and local OCR was unavailable; publication eligibility is zero. Per-PDF URLs, provenance, metadata, license status, and SHA-256 are in `content/ingestion/manifest.json`; the count matrix and detailed results are in `content/reconciliation/`. The PDFs report copying disabled, printing enabled; the source license is not established. Do not promote these candidates until OCR/text review, edition identification, rights clearance, Guru approval, and coverage reconciliation are complete. No profile reference audio has been supplied. Existing nine excerpts remain governed by the source document and `content/rigveda_review_manifest.json`.
