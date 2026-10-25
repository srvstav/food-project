"""Integration tests against the local `mess` database (run db/setup.sh first)."""
import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from db import connect
from main import app

client = TestClient(app)


def _phone() -> str:
    return f"9{random.randint(0, 10**9 - 1):09d}"


def _login(phone: str) -> dict[str, str]:
    otp = client.post("/auth/request-otp", json={"phone": phone}).json()["dev_otp"]
    token = client.post("/auth/verify-otp", json={"phone": phone, "otp": otp}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _forecast(meal: str, mess: str) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT booked FROM v_daily_forecast WHERE meal_date = CURDATE() AND meal = %s AND mess = %s",
            (meal, mess),
        )
        row = cur.fetchone()
    return int(row["booked"]) if row else 0


@pytest.mark.parametrize("phone", ["12345", "5876543210", "98765432100", "abcdefghij"])
def test_bad_phone_rejected(phone: str) -> None:
    assert client.post("/auth/request-otp", json={"phone": phone}).status_code == 422


def test_wrong_otp_then_lockout() -> None:
    phone = _phone()
    client.post("/auth/request-otp", json={"phone": phone})
    for _ in range(5):
        assert client.post("/auth/verify-otp", json={"phone": phone, "otp": "000000"}).status_code in (400, 429)
    assert client.post("/auth/verify-otp", json={"phone": phone, "otp": "000000"}).status_code == 429


def test_otp_single_use() -> None:
    phone = _phone()
    otp = client.post("/auth/request-otp", json={"phone": phone}).json()["dev_otp"]
    assert client.post("/auth/verify-otp", json={"phone": phone, "otp": otp}).status_code == 200
    assert client.post("/auth/verify-otp", json={"phone": phone, "otp": otp}).status_code == 400


def test_booking_needs_login() -> None:
    body = {"meal_date": str(date.today()), "slot_id": 1, "mess_id": 1}
    assert client.post("/bookings", json=body).status_code == 401
    assert client.post("/bookings", json=body, headers={"Authorization": "Bearer x.y"}).status_code == 401


def test_rebooking_changes_choice_and_skip_is_not_counted() -> None:
    auth = _login(_phone())
    today = str(date.today())
    dove, spring = _forecast("Dinner", "BluDove"), _forecast("Dinner", "BluSpring")

    client.post("/bookings", json={"meal_date": today, "slot_id": 4, "mess_id": 1}, headers=auth)
    assert _forecast("Dinner", "BluDove") == dove + 1

    client.post("/bookings", json={"meal_date": today, "slot_id": 4, "mess_id": 2}, headers=auth)
    assert (_forecast("Dinner", "BluDove"), _forecast("Dinner", "BluSpring")) == (dove, spring + 1)

    client.post("/bookings", json={"meal_date": today, "slot_id": 4}, headers=auth)
    assert (_forecast("Dinner", "BluDove"), _forecast("Dinner", "BluSpring")) == (dove, spring)

    mine = client.get(f"/bookings/me?meal_date={today}", headers=auth).json()["bookings"]
    assert mine == [{"slot_id": 4, "mess_id": None, "status": "skipped"}]


def test_date_window_and_unknown_ids() -> None:
    auth = _login(_phone())
    too_far = str(date.today() + timedelta(days=8))
    assert client.post("/bookings", json={"meal_date": too_far, "slot_id": 1, "mess_id": 1}, headers=auth).status_code == 400
    today = str(date.today())
    assert client.post("/bookings", json={"meal_date": today, "slot_id": 9, "mess_id": 1}, headers=auth).status_code == 400
    assert client.post("/bookings", json={"meal_date": today, "slot_id": 1, "mess_id": 9}, headers=auth).status_code == 400


def test_cook_for_is_booked_plus_30_percent() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT booked, cook_for FROM v_daily_forecast")
        rows = cur.fetchall()
    assert rows, "expected bookings from earlier tests"
    for r in rows:
        assert r["cook_for"] == -(-r["booked"] * 13 // 10)  # ceil(booked * 1.3)
