"""Repository Pattern: every SQL statement lives here, all parameterized."""
from datetime import date, datetime
from typing import Any

from pymysql.connections import Connection

Row = dict[str, Any]


def latest_otp(conn: Connection, phone: str) -> Row | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, code_hash, expires_at, attempts, used_at, created_at "
            "FROM otp_codes WHERE phone = %s ORDER BY id DESC LIMIT 1",
            (phone,),
        )
        return cur.fetchone()


def insert_otp(conn: Connection, phone: str, code_hash: str, expires_at: datetime) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO otp_codes (phone, code_hash, expires_at) VALUES (%s, %s, %s)",
            (phone, code_hash, expires_at),
        )


def bump_otp_attempts(conn: Connection, otp_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = %s", (otp_id,))


def mark_otp_used(conn: Connection, otp_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE otp_codes SET used_at = CURRENT_TIMESTAMP(3) WHERE id = %s", (otp_id,))


def login_student(conn: Connection, phone: str) -> int:
    """Create the student on first login, then stamp last_login_at (fires the LOGIN trigger)."""
    with conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO students (phone) VALUES (%s)", (phone,))
        cur.execute("UPDATE students SET last_login_at = CURRENT_TIMESTAMP(3) WHERE phone = %s", (phone,))
        cur.execute("SELECT id FROM students WHERE phone = %s", (phone,))
        row = cur.fetchone()
    assert row is not None
    return int(row["id"])


def student_phone(conn: Connection, student_id: int) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT phone FROM students WHERE id = %s", (student_id,))
        row = cur.fetchone()
    return row["phone"] if row else None


def menu(conn: Connection) -> list[Row]:
    # No params passed, so PyMySQL does no %-formatting: single % here, %% in the other queries.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT m.id AS mess_id, m.name AS mess, s.id AS slot_id, s.code AS slot_code, s.name AS slot, "
            "TIME_FORMAT(s.starts_at, '%H:%i') AS starts_at, TIME_FORMAT(s.ends_at, '%H:%i') AS ends_at, "
            "i.dish "
            "FROM menu_items i JOIN messes m ON m.id = i.mess_id JOIN meal_slots s ON s.id = i.slot_id "
            "ORDER BY s.id, m.id, i.id"
        )
        return list(cur.fetchall())


def slot_and_mess_exist(conn: Connection, slot_id: int, mess_id: int | None) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM meal_slots WHERE id = %s", (slot_id,))
        if cur.fetchone() is None:
            return False
        if mess_id is None:
            return True
        cur.execute("SELECT 1 FROM messes WHERE id = %s", (mess_id,))
        return cur.fetchone() is not None


def upsert_booking(conn: Connection, student_id: int, meal_date: date, slot_id: int, mess_id: int | None) -> None:
    status = "booked" if mess_id is not None else "skipped"
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bookings (student_id, meal_date, slot_id, mess_id, status) "
            "VALUES (%s, %s, %s, %s, %s) AS new "
            "ON DUPLICATE KEY UPDATE mess_id = new.mess_id, status = new.status",
            (student_id, meal_date, slot_id, mess_id, status),
        )


def bookings_for(conn: Connection, student_id: int, meal_date: date) -> list[Row]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT slot_id, mess_id, status FROM bookings WHERE student_id = %s AND meal_date = %s",
            (student_id, meal_date),
        )
        return list(cur.fetchall())


def recent_activity(conn: Connection, limit: int) -> list[Row]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, DATE_FORMAT(at, '%%H:%%i:%%s') AS at, event, detail "
            "FROM activity_log ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        return list(cur.fetchall())


def forecast(conn: Connection, meal_date: date) -> list[Row]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT mess, meal, booked, cook_for FROM v_daily_forecast "
            "WHERE meal_date = %s ORDER BY slot_order, mess",
            (meal_date,),
        )
        return list(cur.fetchall())
