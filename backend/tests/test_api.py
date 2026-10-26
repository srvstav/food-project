"""Integration tests against the configured `mess` database (run setup first).

They add rows to the real database. Run `reset.bat` / `python setup.py reset` afterwards for a clean demo.
"""
import dataclasses
import random
import time
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import auth
import firebase
from config import settings, today
from db import connect
from main import app

client = TestClient(app)
STAFF = {"X-Staff-Pin": settings.staff_pin}
PROJECT = "mess-test"

# Stand-in for Google's signing key: tokens are signed and checked for real, just with our key.
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PEM = _KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


@pytest.fixture(autouse=True)
def fake_firebase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(firebase, "_key_for", lambda kid: _KEY.public_key() if kid == "test" else None)
    monkeypatch.setattr(auth, "settings", dataclasses.replace(settings, firebase_project_id=PROJECT))


def _id_token(phone: str, project: str = PROJECT, kid: str = "test", age: int = 0) -> str:
    t = int(time.time()) - age
    claims = {"iss": f"https://securetoken.google.com/{project}", "aud": project, "sub": f"uid-{phone}",
              "iat": t, "exp": t + 3600, "auth_time": t, "phone_number": f"+91{phone}"}
    return jwt.encode(claims, _PEM, algorithm="RS256", headers={"kid": kid})


def _phone() -> str:
    """A new student on the roster (as the mess office would add one in Workbench)."""
    phone = f"8{random.randint(0, 10**9 - 1):09d}"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, year_of_study, "
            "hostel_id, room_no, joined_on) VALUES (%s, 'Test Student', 'F', %s, %s, 1, 2, 13, '101', '2025-07-20')",
            (f"99{phone[-7:]}", phone, f"test.{phone}@example.com"))
        conn.commit()
    return phone


def _login(phone: str) -> dict[str, str]:
    token = client.post("/auth/login", json={"id_token": _id_token(phone)}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _q(sql: str, args: tuple = ()) -> dict | None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def _booked(meal: str, mess: str) -> int:
    row = _q("SELECT booked FROM v_daily_forecast WHERE meal_date = %s AND meal = %s AND mess = %s",
             (today(), meal, mess))
    return int(row["booked"]) if row else 0


# ---------- login ----------

def test_login_returns_roster_profile_and_is_logged_by_trigger() -> None:
    phone = _phone()
    r = client.post("/auth/login", json={"id_token": _id_token(phone)})
    assert r.status_code == 200
    me = r.json()["student"]
    assert me["full_name"] == "Test Student" and me["hostel"] == "G1" and me["programme"] == "BTECH-CSE"
    auth_header = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/me", headers=auth_header).json()["student"]["phone"] == phone
    events = _q("SELECT GROUP_CONCAT(a.event ORDER BY a.id) AS e FROM activity_log a "
                "JOIN students s ON s.id = a.student_id WHERE s.phone = %s", (phone,))
    assert events["e"] == "ENROL,LOGIN"


def test_roster_check_before_sms_and_its_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    phone = _phone()
    assert client.post("/auth/check", json={"phone": phone}).json() == {"on_roster": True}  # real-SMS mode: no code returned
    assert client.post("/auth/check", json={"phone": "12345"}).status_code == 422
    monkeypatch.setattr(auth, "_checks", auth.defaultdict(auth.deque))
    codes = [client.post("/auth/check", json={"phone": phone}).status_code for _ in range(auth.CHECKS_PER_WINDOW + 1)]
    assert codes[-1] == 429 and set(codes[:-1]) == {200}


def test_new_number_joins_the_roster_on_first_login() -> None:
    phone = f"6{random.randint(0, 10**9 - 1):09d}"
    assert client.post("/auth/check", json={"phone": phone}).json()["on_roster"] is True
    r = client.post("/auth/login", json={"id_token": _id_token(phone)})
    assert r.status_code == 200 and r.json()["student"]["full_name"] == f"Guest {phone[-4:]}"
    assert client.post("/auth/login", json={"id_token": _id_token(phone)}).status_code == 200  # second login: same student


@pytest.mark.parametrize("bad", [
    lambda p: _id_token(p, project="someone-else"),   # token from another Firebase project
    lambda p: _id_token(p, kid="unknown"),            # not signed by a Google key
    lambda p: _id_token(p, age=7200),                 # expired
    lambda p: _id_token(p)[:-4] + "AAAA",             # tampered signature
])
def test_forged_or_stale_tokens_are_refused(bad) -> None:
    assert client.post("/auth/login", json={"id_token": bad(_phone())}).status_code == 401


def test_roster_rules_live_in_the_database() -> None:
    import pymysql
    with connect() as conn, conn.cursor() as cur, pytest.raises(pymysql.err.OperationalError, match="other gender"):
        cur.execute("INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, year_of_study, "
                    "hostel_id, room_no, joined_on) VALUES ('990000001', 'X Y', 'M', '8000000001', 'x@y.in', 1, 1, 13, "
                    "'1', '2025-07-20')")


# ---------- menu ----------

def test_menu_has_both_messes_for_all_four_meals() -> None:
    r = client.get("/menu")
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert [s["name"] for s in slots] == ["Breakfast", "Lunch", "Hi-Tea", "Dinner"]
    assert slots[0]["starts_at"] == "07:30"
    assert all(len(s["messes"]) == 2 and all(m["dishes"] for m in s["messes"]) for s in slots)


def test_site_and_dashboards_are_served() -> None:
    for path in ("/", "/dashboard.html", "/staff.html"):
        assert client.get(path).status_code == 200, path
    live = client.get("/admin/live")
    assert live.status_code == 200 and live.json()["roster"]["students"] >= 1200


# ---------- booking ----------

def test_booking_needs_login() -> None:
    body = {"meal_date": str(today()), "slot_id": 1, "mess_id": 1}
    assert client.post("/bookings", json=body).status_code == 401
    assert client.post("/bookings", json=body, headers={"Authorization": "Bearer x.y"}).status_code == 401


def test_rebooking_changes_choice_and_skip_is_not_counted() -> None:
    auth = _login(_phone())
    d = str(today())
    dove, spring = _booked("Dinner", "BluDove"), _booked("Dinner", "BluSpring")

    client.post("/bookings", json={"meal_date": d, "slot_id": 4, "mess_id": 1}, headers=auth)
    assert _booked("Dinner", "BluDove") == dove + 1

    client.post("/bookings", json={"meal_date": d, "slot_id": 4, "mess_id": 2}, headers=auth)
    assert (_booked("Dinner", "BluDove"), _booked("Dinner", "BluSpring")) == (dove, spring + 1)

    client.post("/bookings", json={"meal_date": d, "slot_id": 4}, headers=auth)
    assert (_booked("Dinner", "BluDove"), _booked("Dinner", "BluSpring")) == (dove, spring)

    mine = client.get(f"/bookings/me?meal_date={d}", headers=auth).json()
    assert mine["bookings"] == [{"slot_id": 4, "mess_id": None, "status": "skipped"}]


def test_date_window_and_unknown_ids() -> None:
    auth = _login(_phone())
    far, d = str(today() + timedelta(days=8)), str(today())
    assert client.post("/bookings", json={"meal_date": far, "slot_id": 1, "mess_id": 1}, headers=auth).status_code == 400
    assert client.post("/bookings", json={"meal_date": d, "slot_id": 9, "mess_id": 1}, headers=auth).status_code == 400
    assert client.post("/bookings", json={"meal_date": d, "slot_id": 1, "mess_id": 9}, headers=auth).status_code == 400


def test_cook_for_is_booked_plus_30_percent() -> None:
    # Own booking, so this passes on a brand-new empty database too.
    client.post("/bookings", json={"meal_date": str(today()), "slot_id": 1, "mess_id": 1}, headers=_login(_phone()))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT booked, cook_for FROM v_daily_forecast")
        rows = cur.fetchall()
    assert rows
    for r in rows:
        assert r["cook_for"] == -(-r["booked"] * 13 // 10)  # ceil(booked * 1.3)


# ---------- pause / resume ----------

def test_pause_releases_meals_blocks_booking_and_resume_restores() -> None:
    auth = _login(_phone())
    day = today() + timedelta(days=2)
    client.post("/bookings", json={"meal_date": str(day), "slot_id": 2, "mess_id": 1}, headers=auth)

    r = client.post("/pause", json={"from_date": str(day), "to_date": str(day + timedelta(days=1))}, headers=auth)
    assert r.status_code == 200
    mine = client.get(f"/bookings/me?meal_date={day}", headers=auth).json()
    assert mine["paused"] is True
    assert mine["bookings"] == [{"slot_id": 2, "mess_id": None, "status": "paused"}]

    # The trigger refuses a booking on a paused day.
    r = client.post("/bookings", json={"meal_date": str(day), "slot_id": 2, "mess_id": 1}, headers=auth)
    assert r.status_code == 409 and "paused" in r.json()["detail"]

    assert client.post("/resume", headers=auth).status_code == 200
    assert client.get("/pause/me", headers=auth).json()["pauses"] == []
    r = client.post("/bookings", json={"meal_date": str(day), "slot_id": 2, "mess_id": 1}, headers=auth)
    assert r.status_code == 200


def test_pause_validation() -> None:
    auth = _login(_phone())
    t = today()
    bad = [
        {"from_date": str(t - timedelta(days=1)), "to_date": str(t)},          # in the past
        {"from_date": str(t + timedelta(days=3)), "to_date": str(t + timedelta(days=1))},  # backwards
        {"from_date": str(t), "to_date": str(t + timedelta(days=90))},          # too long
    ]
    for body in bad:
        assert client.post("/pause", json=body, headers=auth).status_code in (400, 422)


# ---------- staff, attendance, donations ----------

def test_staff_needs_pin() -> None:
    assert client.get("/staff/check").status_code == 403
    assert client.get("/staff/check", headers={"X-Staff-Pin": "000000x"}).status_code == 403
    assert client.get("/staff/check", headers=STAFF).status_code == 200


def test_serve_booked_walk_in_and_twice() -> None:
    booked_phone, walk_phone = _phone(), _phone()
    client.post("/bookings", json={"meal_date": str(today()), "slot_id": 3, "mess_id": 2}, headers=_login(booked_phone))

    r = client.post("/staff/serve", json={"phone": booked_phone, "mess_id": 2, "slot_id": 3}, headers=STAFF).json()
    assert r["booked_here"] is True and r["name"] == "Test Student"
    r = client.post("/staff/serve", json={"phone": walk_phone, "mess_id": 2, "slot_id": 3}, headers=STAFF).json()
    assert r["booked_here"] is False and r["booking"] == "none"
    again = client.post("/staff/serve", json={"phone": booked_phone, "mess_id": 2, "slot_id": 3}, headers=STAFF)
    assert again.status_code == 409
    unknown = client.post("/staff/serve", json={"phone": "6000000000", "mess_id": 2, "slot_id": 3}, headers=STAFF)
    assert unknown.status_code == 404


def test_meal_summary_math_and_close_meal() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_meal_summary")
        rows = cur.fetchall()
    for r in rows:
        assert r["cooked"] == -(-r["booked"] * 13 // 10)
        assert r["buffer_left"] == max(r["cooked"] - r["booked"] - r["walk_ins"], 0)
        assert r["donate"] == min(max(r["cooked"] - r["served"], 0), r["buffer_left"] + r["no_shows"] // 2)

    r = client.post("/staff/close-meal", json={"meal_date": str(today()), "slot_id": 3}, headers=STAFF)
    assert r.status_code == 200
    expected = {(x["mess"]): x["donate"] for x in rows if x["meal_date"] == today() and x["slot_id"] == 3 and x["donate"] > 0}
    assert {d["mess"]: d["portions"] for d in r.json()["donations"]} == expected


def test_demo_mode_shows_the_code_and_logs_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "settings", dataclasses.replace(settings, firebase_project_id=None))
    phone = _phone()
    code = client.post("/auth/check", json={"phone": phone}).json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/auth/demo-verify", json={"phone": phone, "otp": wrong}).status_code == 400
    r = client.post("/auth/demo-verify", json={"phone": phone, "otp": code})
    assert r.status_code == 200 and r.json()["student"]["phone"] == phone
    assert client.post("/auth/demo-verify", json={"phone": phone, "otp": code}).status_code == 400  # one use


def test_demo_codes_are_off_when_firebase_is_on() -> None:
    assert client.post("/auth/demo-verify", json={"phone": _phone(), "otp": "123456"}).status_code == 403
