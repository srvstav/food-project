"""Repository Pattern: every SQL statement lives here, and all of them use parameters (no string-built SQL).

PyMySQL only %-formats a query when parameters are passed (args is not None), so a literal %
is written as %% in queries with parameters and as % in queries without.
"""
from datetime import date, datetime
from typing import Any

from pymysql.connections import Connection

Row = dict[str, Any]


def _one(conn: Connection, sql: str, args: tuple | None = None) -> Row | None:
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def _all(conn: Connection, sql: str, args: tuple | None = None) -> list[Row]:
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchall())


def _exec(conn: Connection, sql: str, args: tuple | None = None) -> int:
    with conn.cursor() as cur:
        return cur.execute(sql, args)


# ---------- OTP and students ----------

def latest_otp(conn: Connection, phone: str) -> Row | None:
    return _one(conn, "SELECT id, code_hash, expires_at, attempts, used_at, created_at "
                      "FROM otp_codes WHERE phone = %s ORDER BY id DESC LIMIT 1", (phone,))


def insert_otp(conn: Connection, phone: str, code_hash: str, created_at: datetime, expires_at: datetime) -> None:
    _exec(conn, "INSERT INTO otp_codes (phone, code_hash, created_at, expires_at) VALUES (%s, %s, %s, %s)",
          (phone, code_hash, created_at, expires_at))


def bump_otp_attempts(conn: Connection, otp_id: int) -> None:
    _exec(conn, "UPDATE otp_codes SET attempts = attempts + 1 WHERE id = %s", (otp_id,))


def mark_otp_used(conn: Connection, otp_id: int) -> None:
    _exec(conn, "UPDATE otp_codes SET used_at = CURRENT_TIMESTAMP(3) WHERE id = %s", (otp_id,))


def login_student(conn: Connection, phone: str) -> int:
    """Create the student on first login, then stamp last_login_at (fires the LOGIN trigger)."""
    _exec(conn, "INSERT IGNORE INTO students (phone) VALUES (%s)", (phone,))
    _exec(conn, "UPDATE students SET last_login_at = CURRENT_TIMESTAMP(3) WHERE phone = %s", (phone,))
    row = _one(conn, "SELECT id FROM students WHERE phone = %s", (phone,))
    assert row is not None
    return int(row["id"])


def student_by_phone(conn: Connection, phone: str) -> Row | None:
    return _one(conn, "SELECT id, phone FROM students WHERE phone = %s", (phone,))


# ---------- menu ----------

def menu(conn: Connection) -> list[Row]:
    return _all(conn,
        "SELECT m.id AS mess_id, m.name AS mess, s.id AS slot_id, s.code AS slot_code, s.name AS slot, "
        "TIME_FORMAT(s.starts_at, '%H:%i') AS starts_at, TIME_FORMAT(s.ends_at, '%H:%i') AS ends_at, i.dish "
        "FROM menu_items i JOIN messes m ON m.id = i.mess_id JOIN meal_slots s ON s.id = i.slot_id "
        "ORDER BY s.id, m.id, i.id")


def slot_exists(conn: Connection, slot_id: int) -> bool:
    return _one(conn, "SELECT 1 AS ok FROM meal_slots WHERE id = %s", (slot_id,)) is not None


def mess_exists(conn: Connection, mess_id: int) -> bool:
    return _one(conn, "SELECT 1 AS ok FROM messes WHERE id = %s", (mess_id,)) is not None


# ---------- bookings ----------

def upsert_booking(conn: Connection, student_id: int, meal_date: date, slot_id: int, mess_id: int | None) -> None:
    status = "booked" if mess_id is not None else "skipped"
    _exec(conn,
        "INSERT INTO bookings (student_id, meal_date, slot_id, mess_id, status) VALUES (%s, %s, %s, %s, %s) AS new "
        "ON DUPLICATE KEY UPDATE mess_id = new.mess_id, status = new.status",
        (student_id, meal_date, slot_id, mess_id, status))


def bookings_for(conn: Connection, student_id: int, meal_date: date) -> list[Row]:
    return _all(conn, "SELECT slot_id, mess_id, status FROM bookings WHERE student_id = %s AND meal_date = %s",
                (student_id, meal_date))


def booking_at(conn: Connection, student_id: int, meal_date: date, slot_id: int) -> Row | None:
    return _one(conn, "SELECT b.mess_id, b.status, m.name AS mess FROM bookings b "
                      "LEFT JOIN messes m ON m.id = b.mess_id "
                      "WHERE b.student_id = %s AND b.meal_date = %s AND b.slot_id = %s",
                (student_id, meal_date, slot_id))


# ---------- pause / resume (stored procedures) ----------

def pause(conn: Connection, student_id: int, from_date: date, to_date: date) -> None:
    _exec(conn, "CALL sp_pause_mess(%s, %s, %s)", (student_id, from_date, to_date))


def resume(conn: Connection, student_id: int, today: date) -> None:
    _exec(conn, "CALL sp_resume_mess(%s, %s)", (student_id, today))


def active_pauses(conn: Connection, student_id: int, today: date) -> list[Row]:
    """Pauses still running or still to come."""
    return _all(conn,
        "SELECT id, from_date, to_date FROM pauses "
        "WHERE student_id = %s AND ended_on IS NULL AND to_date >= %s ORDER BY from_date",
        (student_id, today))


def is_paused(conn: Connection, student_id: int, d: date) -> bool:
    return _one(conn,
        "SELECT 1 AS ok FROM pauses WHERE student_id = %s AND %s BETWEEN from_date AND to_date "
        "AND (ended_on IS NULL OR %s < ended_on) LIMIT 1", (student_id, d, d)) is not None


# ---------- attendance and donations ----------

def serve(conn: Connection, student_id: int, meal_date: date, slot_id: int, mess_id: int) -> None:
    _exec(conn, "INSERT INTO attendance (student_id, meal_date, slot_id, mess_id) VALUES (%s, %s, %s, %s)",
          (student_id, meal_date, slot_id, mess_id))


def close_meal(conn: Connection, meal_date: date, slot_id: int) -> None:
    _exec(conn, "CALL sp_close_meal(%s, %s)", (meal_date, slot_id))


def meal_summary(conn: Connection, meal_date: date) -> list[Row]:
    return _all(conn,
        "SELECT mess_id, mess, slot_id, meal, booked, cooked, served, no_shows, walk_ins, buffer_left, donate "
        "FROM v_meal_summary WHERE meal_date = %s ORDER BY slot_id, mess_id", (meal_date,))


def donations_on(conn: Connection, meal_date: date) -> list[Row]:
    return _all(conn,
        "SELECT d.slot_id, ms.name AS meal, m.name AS mess, n.name AS ngo, n.area, d.portions "
        "FROM donations d JOIN messes m ON m.id = d.mess_id JOIN meal_slots ms ON ms.id = d.slot_id "
        "JOIN ngos n ON n.id = d.ngo_id WHERE d.meal_date = %s ORDER BY d.slot_id, d.mess_id", (meal_date,))


def ngo_totals(conn: Connection) -> list[Row]:
    return _all(conn, "SELECT name, area, deliveries, portions FROM v_ngo_totals ORDER BY portions DESC, name")


# ---------- dashboards ----------

def recent_activity(conn: Connection, limit: int) -> list[Row]:
    return _all(conn,
        "SELECT id, DATE_FORMAT(at, '%%H:%%i:%%s') AS at, event, detail "
        "FROM activity_log ORDER BY id DESC LIMIT %s", (limit,))


def forecast(conn: Connection, meal_date: date) -> list[Row]:
    return _all(conn,
        "SELECT mess, meal, booked, cook_for FROM v_daily_forecast "
        "WHERE meal_date = %s ORDER BY slot_id, mess_id", (meal_date,))
