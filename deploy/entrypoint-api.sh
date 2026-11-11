#!/bin/sh
set -eu
echo "Running database migrations"
alembic upgrade head
echo "Seeding Guru catalog (insert-only; never overwrites verse text)"
python -m app.bootstrap
echo "Starting API"
LOG_LEVEL_LC=$(printf '%s' "${LOG_LEVEL:-info}" | tr 'A-Z' 'a-z')
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level "$LOG_LEVEL_LC"
