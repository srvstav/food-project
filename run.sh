#!/usr/bin/env bash
# Starts the API. Live dashboard: http://127.0.0.1:8000/admin
set -euo pipefail
cd "$(dirname "$0")/backend"
[ -f .env ] || { echo "Run ./db/setup.sh first"; exit 1; }
[ -d .venv ] || { uv venv -q -p 3.13 .venv && uv pip install -q -p .venv -r requirements.txt; }
exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
