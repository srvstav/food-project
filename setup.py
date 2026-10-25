"""
One setup script for Windows, macOS and the cloud.

  python setup.py local     build the database on this laptop's MySQL (asks for the root password)
  python setup.py cloud     build the database on the cloud MySQL in backend/.env.cloud
  python setup.py reset     wipe and rebuild the local database (re-uses host/port/user)

It creates database `mess`, loads db/schema.sql and db/seed.sql, makes a
least-privilege user `mess_app`, and writes backend/.env for the API.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import pymysql
except ImportError:
    sys.exit("pymysql is missing. Run setup.bat (Windows) or: pip install -r backend/requirements.txt")

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
SAVED = BACKEND / ".setup.json"  # remembers host/port/user (never the root password)


def split_sql(text: str) -> list[str]:
    """Split a .sql file into statements, honouring DELIMITER lines like the mysql client does."""
    statements, buf, delim = [], [], ";"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delim = stripped.split(None, 1)[1]
            continue
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        if stripped.endswith(delim):
            stmt = "\n".join(buf).rstrip()[: -len(delim)].strip()
            if stmt:
                statements.append(stmt)
            buf = []
    if "\n".join(buf).strip():
        statements.append("\n".join(buf).strip())
    return statements


def run_file(conn: pymysql.connections.Connection, path: Path) -> int:
    count = 0
    with conn.cursor() as cur:
        for stmt in split_sql(path.read_text(encoding="utf-8")):
            try:
                cur.execute(stmt)
            except pymysql.MySQLError as e:
                first = stmt.splitlines()[0][:80]
                sys.exit(f"\nFailed in {path.name} at: {first}\n  {e}")
            count += 1
    conn.commit()
    return count


def connect(host: str, port: int, user: str, password: str, ssl_ca: str | None, database: str | None = None):
    kwargs = dict(host=host, port=port, user=user, password=password, charset="utf8mb4",
                  autocommit=False, connect_timeout=15)
    if database:
        kwargs["database"] = database
    if ssl_ca:
        kwargs["ssl"] = {"ca": ssl_ca}
    return pymysql.connect(**kwargs)


def check_can_create_triggers(conn, user: str) -> None:
    """With binary logging on, MySQL only lets SUPER users create triggers/procedures,
    unless log_bin_trust_function_creators is ON. Fail early with a clear message."""
    with conn.cursor() as cur:
        cur.execute("SELECT @@log_bin, @@log_bin_trust_function_creators, VERSION()")
        log_bin, trusted, version = cur.fetchone()
        cur.execute("SHOW GRANTS")
        grants = " ".join(g[0] for g in cur.fetchall()).upper()
    print(f"-> MySQL {version}")
    has_super = "SUPER" in grants or "ALL PRIVILEGES ON *.*" in grants
    if log_bin and not trusted and not has_super:
        sys.exit(
            f"\nThis MySQL server will refuse to create triggers for user '{user}':\n"
            "  binary logging is ON, log_bin_trust_function_creators is OFF, and the user lacks SUPER.\n"
            "Fix: turn ON 'log_bin_trust_function_creators' in the provider's MySQL settings,\n"
            "or use a MySQL where the admin has SUPER (any local install, Railway)."
        )


def build(host: str, port: int, admin_user: str, admin_pass: str, ssl_ca: str | None) -> dict[str, str]:
    print(f"-> Connecting to MySQL at {host}:{port} as {admin_user} ...")
    try:
        conn = connect(host, port, admin_user, admin_pass, ssl_ca)
    except pymysql.MySQLError as e:
        hint = ""
        if "Access denied" in str(e):
            hint = "\n  The password is wrong. Use the root password you chose when installing MySQL."
        elif "Can't connect" in str(e) or "timed out" in str(e):
            hint = "\n  MySQL is not running. On Windows: press Win+R, type services.msc, start 'MySQL80'."
        sys.exit(f"Could not connect: {e}{hint}")

    with conn:
        check_can_create_triggers(conn, admin_user)
        n = run_file(conn, ROOT / "db" / "schema.sql")
        print(f"-> Built schema ({n} statements: tables, triggers, procedures, views)")
        conn.select_db("mess")
        n = run_file(conn, ROOT / "db" / "seed.sql")
        print(f"-> Loaded sample data ({n} statements: 2 messes, 4 meals, menus, NGOs)")

        app_pass = secrets.token_urlsafe(18)
        # Cloud: the API connects from another server. Local: only from this machine
        # (both names, because some MySQL installs skip name resolution for 127.0.0.1).
        app_hosts = ["%"] if ssl_ca else ["localhost", "127.0.0.1"]
        with conn.cursor() as cur:
            for h in app_hosts:
                cur.execute(f"DROP USER IF EXISTS 'mess_app'@'{h}'")
                cur.execute(f"CREATE USER 'mess_app'@'{h}' IDENTIFIED BY %s", (app_pass,))
                # Least privilege: read/write rows and call procedures. No DELETE, DROP or ALTER.
                cur.execute(f"GRANT SELECT, INSERT, UPDATE, EXECUTE ON mess.* TO 'mess_app'@'{h}'")
        conn.commit()
        print("-> Created user mess_app (SELECT, INSERT, UPDATE, EXECUTE only)")

    return {
        "DB_HOST": "127.0.0.1" if host == "localhost" else host,
        "DB_PORT": str(port),
        "DB_USER": "mess_app",
        "DB_PASSWORD": app_pass,
        "DB_NAME": "mess",
    }


def write_env(db: dict[str, str], ssl_ca_pem: str | None, target: Path) -> dict[str, str]:
    env = {
        **db,
        "TOKEN_SECRET": secrets.token_hex(32),
        "STAFF_PIN": f"{secrets.randbelow(10**6):06d}",
        "OTP_MODE": "dev",
        "ALLOWED_ORIGINS": "*",
    }
    if ssl_ca_pem:
        env["DB_SSL_CA_PEM"] = ssl_ca_pem.replace("\n", "\\n")
    target.write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
    return env


def cmd_local(ask: bool) -> None:
    saved = json.loads(SAVED.read_text()) if SAVED.exists() else {}
    host = saved.get("host", "127.0.0.1")
    port = int(saved.get("port", 3306))
    user = saved.get("user", "root")
    if ask:
        print("MySQL on this laptop. Press Enter to accept the value in [brackets].")
        host = input(f"  Host [{host}]: ").strip() or host
        port = int(input(f"  Port [{port}]: ").strip() or port)
        user = input(f"  Admin user [{user}]: ").strip() or user
    # MYSQL_ROOT_PASSWORD lets scripts and CI run setup without typing (it may be empty).
    password = os.environ.get("MYSQL_ROOT_PASSWORD")
    if password is None:
        password = getpass.getpass(f"  Password for {user} (typing is hidden; blank if none): ")
    SAVED.write_text(json.dumps({"host": host, "port": port, "user": user}))

    db = build(host, port, user, password, None)
    env = write_env(db, None, BACKEND / ".env")
    print("\nOK: Local database ready. API settings saved to backend/.env")
    print(f"  Staff PIN (for staff.html): {env['STAFF_PIN']}")
    print("  Next: double-click start.bat (Windows) or run ./start.sh, then open http://127.0.0.1:8000")


def cmd_cloud() -> None:
    env_file = BACKEND / ".env.cloud"
    ca_file = BACKEND / "ca.pem"
    if not env_file.exists():
        sys.exit("Create backend/.env.cloud with one line:  DATABASE_URL=mysql://avnadmin:...@host:port/defaultdb?ssl-mode=REQUIRED")
    if not ca_file.exists():
        sys.exit("Save the Aiven CA certificate as backend/ca.pem")
    m = re.search(r"^DATABASE_URL=(.+)$", env_file.read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit("backend/.env.cloud must contain a line starting with DATABASE_URL=")
    url = urlparse(m.group(1).strip())
    if url.scheme not in ("mysql", "mysql2") or not url.hostname:
        sys.exit("DATABASE_URL should look like mysql://user:pass@host:port/db")

    db = build(url.hostname, url.port or 3306, unquote(url.username or ""), unquote(url.password or ""), str(ca_file))
    env = write_env(db, ca_file.read_text(encoding="utf-8"), BACKEND / ".env.render")
    print("\nOK: Cloud database ready.")
    print("  Render settings saved to backend/.env.render - paste them into Render -> Environment.")
    print(f"  Staff PIN: {env['STAFF_PIN']}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"
    if mode == "local":
        cmd_local(ask=True)
    elif mode == "reset":
        cmd_local(ask=False)
    elif mode == "cloud":
        cmd_cloud()
    else:
        sys.exit(__doc__)
