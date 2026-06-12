#!/bin/bash
set -e

alembic upgrade head

python -m seed

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
