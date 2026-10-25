#!/usr/bin/env bash
# Builds the database, seeds it, and creates a least-privilege app user.
# The app password is random and only written to backend/.env (gitignored).
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT=(mysql -u root ${MYSQL_ROOT_PASSWORD:+-p"$MYSQL_ROOT_PASSWORD"})
APP_PASS="$(openssl rand -hex 16)"
SECRET="$(openssl rand -hex 32)"

"${ROOT[@]}" < db/schema.sql
"${ROOT[@]}" < db/seed.sql
"${ROOT[@]}" <<SQL
DROP USER IF EXISTS 'mess_app'@'localhost';
CREATE USER 'mess_app'@'localhost' IDENTIFIED BY '${APP_PASS}';
GRANT SELECT, INSERT, UPDATE ON mess.* TO 'mess_app'@'localhost';
SQL

cat > backend/.env <<ENV
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=mess_app
DB_PASSWORD=${APP_PASS}
DB_NAME=mess
TOKEN_SECRET=${SECRET}
# dev = OTP is shown on the page (no SMS gateway yet)
OTP_MODE=dev
ALLOWED_ORIGINS=https://srvstav.github.io,http://localhost:5500,http://127.0.0.1:5500
ENV

echo "Database 'mess' ready. backend/.env written."
