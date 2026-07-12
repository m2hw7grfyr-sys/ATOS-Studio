#!/usr/bin/env sh
set -eu

PORT="${STUDIO_PORT:-8502}"
exec uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --reload

