# Architecture and repository layout

The repository uses a layered backend and a feature-first Flutter client. This keeps API, persistence, business rules, presentation, and media responsibilities separate while allowing lesson work to stay grouped by feature.

```text
backend/
  app/
    api/          HTTP controllers and route wiring
    schemas/      request/response DTOs and validation
    models/       SQLAlchemy persistence models
    db/           database setup and sessions
    services/     business rules and integrations
    services/engines/ replaceable speech/evaluation engines
    workers/      asynchronous jobs
  alembic/        database migrations
  tests/          backend tests
  poc/            isolated ASR/alignment experiments (large model caches ignored)

mobile/
  lib/
    core/         app configuration, shared platform helpers and theme
    data/         API and persistence access
    state/        app/session state
    features/     feature screens and their presentation/controller state
    widgets/      shared UI components
  assets/
    audio/
      guru_reference/  full Guru reference recordings
      guru_words/      optional per-word clips
    videos/            lesson videos

content/          lesson source data, review manifests and evaluation artifacts
scripts/          ingestion and repository/deployment utilities
deploy/           deployment-specific configuration
```

## MVC responsibility map

- **Model:** `backend/app/models`, plus Flutter data/state objects and API response models.
- **Controller:** `backend/app/api`; on Flutter, feature state and actions in `mobile/lib/features` call data services and coordinate UI state.
- **View:** Flutter widgets and pages in `mobile/lib/features` and reusable UI in `mobile/lib/widgets`.
- **Service layer:** `backend/app/services` and `mobile/lib/data` contain business and network operations; views should not own persistence or HTTP details.

The Flutter client is feature-first rather than a global `models/controllers/views` tree. Keep each feature cohesive; when a feature grows, split it into `view/`, `controller/`, and `model/` files inside that feature instead of creating cross-app MVC folders. The backend already follows explicit controller/schema/model/service layers.

## Media and content

Bundled media is intentionally versioned with the app: the nine lesson videos and nine Guru reference audio files are under `mobile/assets/`. Optional per-word clips belong under `mobile/assets/audio/guru_words/<lesson-id>/`. Keep the source mapping and review metadata under `content/`. Do not store learner recordings, database files, credentials, or downloaded ASR model weights in the source tree.

## Local setup

See [README.md](README.md) for local development and [DEPLOYMENT.md](DEPLOYMENT.md) for deployment. Copy `.env.example` to `.env` for local use; `.env` and signing keys are ignored by Git. Large model weights are downloaded or provisioned separately and are excluded from version control.

Large generated PDF ingestion and reconciliation exports are also ignored to keep normal GitHub pushes manageable. Their generating scripts, schemas, manifests, summaries and review dashboards remain in the repository; the local export files are left in place.
