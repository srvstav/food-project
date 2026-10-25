"""Integration tests against the configured `mess` database (run setup first).

They add rows to the real database. Run `reset.bat` / `python setup.py reset` afterwards for a clean demo.
"""
import random
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from config import settings, today
from db import connect
from main import app

client = TestClient(app)
STAFF = {"X-Staff-Pin": settings.staff_pin}


def _phone() -> str:
    return f"8{random.randint(0, 10**9 - 1):09d}"


def _login(phone: str) -> dict[str, str]:
    otp = client.post("/auth/request-otp", json={"phone": phone}).json()["dev_otp"]
    token = client.post("/auth/verify-otp", json={"phone": phone, "otp": otp}).json()["token"]
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

@pytest.mark.parametrize("phone", ["12345", "5876543210", "98765432100", "abcdefghij"])
def test_bad_phone_rejected(phone: str) -> None:
    assert client.post("/auth/request-otp", json={"phone": phone}).status_code == 422


def test_wrong_otp_then_lockout() -> None:
    phone = _phone()
    client.post("/auth/request-otp", json={"phone": phone})
    for _ in range(5):
        assert client.post("/auth/verify-otp", json={"phone": phone, "otp": "000000"}).status_code in (400, 429)
    assert client.post("/auth/verify-otp", json={"phone": phone, "otp": "000000"}).status_code == 429


def test_otp_single_use_and_resend_wait() -> None:
    phone = _phone()
    otp = client.post("/auth/request-otp", json={"phone": phone}).json()["dev_otp"]
    assert client.post("/auth/request-otp", json={"phone": phone}).status_code == 429
    assert client.post("/auth/verify-otp", json={"phone": phone, "otp": otp}).status_code == 200
    assert client.post("/auth/verify-otp", json={"phone": phone, "otp": otp}).status_code == 400


def test_login_is_logged_by_trigger() -> None:
    phone = _phone()
    _login(phone)
    events = _q("SELECT GROUP_CONCAT(event ORDER BY id) AS e FROM activity_log WHERE detail LIKE %s", (f"%{phone}%",))
    assert events["e"] == "SIGNUP,LOGIN"


# ---------- menu ----------

def test_menu_has_both_messes_for_all_four_meals() -> None:
    r = client.get("/menu")
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert [s["name"] for s in slots] == ["Breakfast", "Lunch", "Hi-Tea", "Dinner"]
    assert slots[0]["starts_at"] == "07:30"
    assert all(len(s["messes"]) == 2 and all(m["dishes"] for m in s["messes"]) for s in slots)


def test_site_and_dashboards_are_served() -> None:
    for path in ("/", "/dashboard.html", "/staff.html", "/project.html"):
        assert client.get(path).status_code == 200, path
    assert client.get("/admin/live").status_code == 200


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
    _login(walk_phone)

    r = client.post("/staff/serve", json={"phone": booked_phone, "mess_id": 2, "slot_id": 3}, headers=STAFF).json()
    assert r["booked_here"] is True
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
