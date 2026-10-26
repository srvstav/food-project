#!/usr/bin/env bash
# macOS/Linux: build (first time) and start the Java API + site on http://127.0.0.1:8000 (Windows: start.bat)
set -euo pipefail
cd "$(dirname "$0")"
[ -f backend/.env ] || { echo "Run: python3 setup.py local"; exit 1; }
[ -f backend/target/mess.jar ] || (cd backend && ./mvnw -q -B package -DskipTests)
exec java -jar backend/target/mess.jar
