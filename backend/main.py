import re
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pymysql.connections import Connection

import auth
import repo
from config import settings
from db import get_conn

app = FastAPI(title="MUJ Mess API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

Conn = Annotated[Connection, Depends(get_conn)]
StudentId = Annotated[int, Depends(auth.current_student)]
Phone = Annotated[str, Field(pattern=r"^[6-9]\d{9}$", description="10-digit Indian mobile")]


class OtpRequest(BaseModel):
    phone: Phone


class OtpVerify(BaseModel):
    phone: Phone
    otp: Annotated[str, Field(pattern=r"^\d{6}$")]


class BookingIn(BaseModel):
    meal_date: date
    slot_id: Annotated[int, Field(ge=1, le=255)]
    mess_id: Annotated[int | None, Field(ge=1, le=255)] = None  # None = skip this meal


def _check_bookable(d: date) -> None:
    today = date.today()
    if not today <= d <= today + timedelta(days=settings.booking_days_ahead):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Pick a date from today to {settings.booking_days_ahead} days ahead")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/request-otp")
def request_otp(body: OtpRequest, conn: Conn) -> dict[str, str]:
    code = auth.issue_otp(conn, body.phone)
    if settings.otp_mode == "dev":
        print(f"[OTP] {body.phone} → {code}", flush=True)
        # TODO(debt): no SMS gateway yet (India needs DLT registration) — the page shows the code instead.
        return {"message": "OTP sent", "dev_otp": code}
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "SMS sending not set up yet")


@app.post("/auth/verify-otp")
def verify_otp(body: OtpVerify, conn: Conn) -> dict[str, str]:
    student_id = auth.verify_otp(conn, body.phone, body.otp)
    return {"token": auth.make_token(student_id), "phone": body.phone}


@app.get("/menu")
def get_menu(conn: Conn) -> dict:
    slots: dict[int, dict] = {}
    for r in repo.menu(conn):
        slot = slots.setdefault(r["slot_id"], {
            "slot_id": r["slot_id"], "code": r["slot_code"], "name": r["slot"],
            "starts_at": r["starts_at"], "ends_at": r["ends_at"], "messes": {},
        })
        mess = slot["messes"].setdefault(r["mess_id"], {"mess_id": r["mess_id"], "name": r["mess"], "dishes": []})
        mess["dishes"].append(r["dish"])
    return {"slots": [{**s, "messes": list(s["messes"].values())} for s in slots.values()]}


@app.get("/bookings/me")
def my_bookings(student_id: StudentId, conn: Conn, meal_date: date = Query(default_factory=date.today)) -> dict:
    return {"meal_date": meal_date, "bookings": repo.bookings_for(conn, student_id, meal_date)}


@app.post("/bookings")
def book(body: BookingIn, student_id: StudentId, conn: Conn) -> dict[str, str]:
    _check_bookable(body.meal_date)
    if not repo.slot_and_mess_exist(conn, body.slot_id, body.mess_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown meal or mess")
    repo.upsert_booking(conn, student_id, body.meal_date, body.slot_id, body.mess_id)
    return {"status": "booked" if body.mess_id else "skipped"}


_PHONE = re.compile(r"\b([6-9]\d)\d{5}(\d{3})\b")


@app.get("/admin/live")
def live(conn: Conn, limit: int = Query(default=25, ge=1, le=100)) -> dict:
    # Phones are masked here because this page is reachable through the public tunnel.
    activity = [{**a, "detail": _PHONE.sub(r"\1xxxxx\2", a["detail"])} for a in repo.recent_activity(conn, limit)]
    return {"activity": activity, "forecast": repo.forecast(conn, date.today())}


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(Path(__file__).parent / "admin.html")
