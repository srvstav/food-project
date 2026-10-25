#!/usr/bin/env bash
# macOS/Linux: start the API + site on http://127.0.0.1:8000 (Windows: start.bat)
set -euo pipefail
cd "$(dirname "$0")/backend"
[ -f .env ] || { echo "Run: python3 setup.py local"; exit 1; }
exec .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
