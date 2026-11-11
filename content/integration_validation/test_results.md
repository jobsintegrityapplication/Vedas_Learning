# Integration test run

Run date: 2026-11-09

## Automated results

- Backend and API suite: **42 passed** in 111 seconds. Run from `backend` with `python -m pytest -p no:cacheprovider --basetemp=./test-tmp`.
- Flutter widget and unit suite: **5 passed**, including the two-second minimum for short shloka recordings.
- Su-śrotā POC checks: **5 passed** for Devanagari normalization, CER/WER distinction, omitted-word error rates, timestamp propagation, and substitution/omission edit alignment.
- Flutter web release build: **passed** with Flutter 3.44.0 after making `window.location.pathname` null-safe in the signup URL cleanup.
- Docker Compose rebuild/start: **passed** for web, API, worker, database, Redis, MailHog, and MinIO; API and web containers reported healthy.
- Local smoke check after startup: `http://127.0.0.1:18080` returned HTTP 200; API `http://127.0.0.1:18000/ready` returned HTTP 200 and `{"status":"ready"}`.
- End-to-end API flow: authenticated learner cannot complete a line without an evaluation or with 89.99%; at 90%, lines unlock in order and lesson completion succeeds only after all lines pass.

## Covered scenarios

- Login/session and access control, learner content, admin content, lesson source preservation, and course endpoints.
- Recording upload validation, learner/Guru storage namespaces, scripted transcript omission/substitution, no-engine fail-closed behavior, and profile-specific reference requirements.
- 90% word-match boundary; pronunciation score is not required to pass; approved Guru reference audio is required; missing reference or ASR does not unlock.
- All nine lesson records expose their source lines; line completion is sequential and requires a passing evaluation; direct lesson-completion events cannot bypass the gate.
- Email-first registration, blocked login before verification, invalid link rejection, verified password setup, email and phone login, replay rejection, and resend invalidation of the old link.
- Short-shloka recording stop after a 2-second minimum; remaining-time rounding and elapsed display formatting.
- Unconfigured ASR returns synchronously as unavailable rather than entering the Celery queue; configured background results can be checked without a 30-second blocking poll.
- Flutter welcome widget and labels across all ten supported interface locales.

## Not established by automated runs

- Actual microphone capture timing, browser playback/replay audio, SMTP delivery into a real mailbox, and hearing that each Guru clip maps to the right word. These require a running UI, browser/device, mail service, and audio hardware.
- Su-śrotā inference on the nine actual Guru clips or a student's recording. This environment does not have the NeMo/PyTorch runtime or checkpoint installed; the local POC harness is isolated and its metrics-only tests passed. No acoustic results were generated.
- Genuine Sanskrit pronunciation assessment. No validated pronunciation/svara engine or approved profile-specific Guru reference data is configured, so real attempts correctly remain unavailable and cannot unlock lessons.
- iOS runtime behavior.

The automated runs validate API flows and duration logic; they do not establish real-world Sanskrit recognition accuracy, actual mailbox delivery, microphone timing, or Guru audio correctness.
