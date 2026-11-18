#!/bin/sh
# Container start: migrate, optionally seed the demo, then serve one worker.
set -e
alembic upgrade head
if [ "${SEED_DEMO_ON_START:-false}" = "true" ]; then
  # Idempotent: does nothing when the demo company already exists.
  python -m app.demo.seed || echo "WARNING: demo seed failed; continuing to start the API"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
