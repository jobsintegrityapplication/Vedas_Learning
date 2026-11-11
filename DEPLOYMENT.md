# Deployment

This document covers local Compose verification, production-oriented server deploy, and store release builds. **Never commit `.env`, keystores, or `key.properties`.** Templates are `.env.example`, `.env.production.example`, and `mobile/android/key.properties.example`.

## Architecture (Compose)

| Service | Role |
| --- | --- |
| `db` | PostgreSQL 16 (Guru content and accounts) |
| `redis` | Celery broker and result backend |
| `minio` | S3-compatible audio storage (Adobe S3Mock in local Compose; MinIO or AWS S3 in production) |
| API bootstrap | Creates the audio bucket if it is missing |
| `mailhog` | Local SMTP capture only |
| `api` | FastAPI: migrate, insert-only Guru seed, HTTP |
| `worker` | Celery evaluation worker |

Health:

- Liveness: `GET /health` (no database)
- Readiness: `GET /ready` (`SELECT 1`)
- Compose waits for Postgres, Redis, MinIO, then API `/ready` before marking the worker ready

Logs: JSON file driver, 10 MB × 3 files per service. Set `LOG_FORMAT=json` for application JSON logs.

## Local verification (this machine)

```powershell
cd veda_learning_poc
copy .env.example .env   # if .env does not exist; do not commit it
docker compose up --build -d
# or
powershell -File scripts/verify-local-deploy.ps1
```

Expected (default host ports; override with `HOST_*_PORT` in `.env` if 8000/5432/6379/9000 are already taken):

- API http://127.0.0.1:8000/health → `{"status":"ok"}`
- API http://127.0.0.1:8000/ready → `{"status":"ready"}`
- Docs (local `APP_ENV` only): http://127.0.0.1:8000/docs
- Mailhog: http://127.0.0.1:8025
- S3 mock: http://127.0.0.1:9000 (S3 API; Docker Hub currently blocks `minio/minio` without login)

Postgres, Redis, object storage, and Mailhog are bound to `127.0.0.1` only. The API is also bound to localhost. Android emulator reaches the host as `10.0.2.2:<HOST_API_PORT>`.

Stop:

```powershell
docker compose down
```

## Production-oriented Compose

Fill `.env` from `.env.production.example` on the server. The process refuses to start if `APP_ENV=production` still has default `SECRET_KEY`, `ADMIN_PASSWORD`, `veda:veda`, or `minioadmin`.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

The overlay:

- Does not publish Postgres, Redis, or MinIO ports
- Disables Mailhog unless profile `mailhog` is enabled
- Sets `EXPOSE_DEV_OTP=false` and JSON logs
- Keeps the API on `127.0.0.1:8000` for a TLS reverse proxy on the host

Put a TLS terminator (Caddy, nginx, or a cloud load balancer) in front of `127.0.0.1:8000`. Serve Guru JSON from the `content/` volume only; never generate verses.

Backups (operator responsibility): volume `pgdata`, volume `miniodata` (Guru reference audio), and a copy of `content/rigveda_lessons.json`.

## Android release (any OS with the Android SDK)

1. Install Flutter stable and accept Android licenses (`flutter doctor --android-licenses`).
2. Create an upload keystore **off this repo**:

```bash
keytool -genkey -v -keystore veda-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias veda
```

3. Copy `mobile/android/key.properties.example` to `mobile/android/key.properties` and point `storeFile` at the `.jks`. Both files are gitignored.
4. Wire signing in `mobile/android/app/build.gradle.kts` (if `key.properties` exists, use the release config; otherwise debug signing is only for local `--release` smoke builds).
5. Build:

```bash
cd mobile
flutter pub get
flutter build appbundle --release --dart-define=API_BASE_URL=https://api.example.com
flutter build apk --release --dart-define=API_BASE_URL=https://api.example.com
```

6. Upload `build/app/outputs/bundle/release/app-release.aab` to Play Console. The Play App Signing certificate is not stored in git.
7. Release builds **must not** use cleartext HTTP. `usesCleartextTraffic` is enabled only in `src/debug` and `src/profile`. Production API must be HTTPS.

## iOS release (requires macOS and Xcode)

Windows and Linux cannot produce a store iOS build. Use a Mac with a current Xcode and an Apple Developer Program account.

1. `cd mobile && flutter pub get`
2. Open `mobile/ios/Runner.xcworkspace` in Xcode (not the `.xcodeproj`).
3. Select the Runner target → Signing & Capabilities: Team, unique Bundle ID, automatically manage signing for development; use a Distribution certificate and App Store provisioning profile for release.
4. Microphone usage string is already in `Info.plist` (`NSMicrophoneUsageDescription`). Production ATS (App Transport Security) expects HTTPS. Do not add arbitrary `NSAllowsArbitraryLoads` for release.
5. Build:

```bash
cd mobile
flutter build ipa --release --dart-define=API_BASE_URL=https://api.example.com
```

6. Distribute with Transporter or Xcode Organizer → Distribute App → App Store Connect. Archive signing identities stay in the Mac keychain, not in this repository.

## Secrets checklist

- [ ] `.env` is not in git (`git check-ignore -v .env`)
- [ ] Production `SECRET_KEY` is unique and ≥ 32 characters
- [ ] Postgres and MinIO passwords are not the Compose lab defaults
- [ ] `EXPOSE_DEV_OTP=false` in production
- [ ] Android `key.properties` and `*.jks` are not in git
- [ ] iOS certificates are in the Apple account / CI secret store, not the repo
