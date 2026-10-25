"""MUJ Mess API — controllers only. SQL lives in repo.py, login logic in auth.py."""
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import pymysql
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from pymysql.connections import Connection

import auth
import repo
from config import settings, today
from db import get_conn

app = FastAPI(title="MUJ Mess API", description="One fee, two messes, book every meal.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Staff-Pin"],
)

Conn = Annotated[Connection, Depends(get_conn)]
StudentId = Annotated[int, Depends(auth.current_student)]
Staff = Annotated[None, Depends(auth.staff_only)]
Phone = Annotated[str, Field(pattern=r"^[6-9]\d{9}$", description="10-digit Indian mobile")]
SlotId = Annotated[int, Field(ge=1, le=255)]
MessId = Annotated[int, Field(ge=1, le=255)]


@app.exception_handler(pymysql.err.OperationalError)
async def db_rule_violation(_: Request, exc: pymysql.err.OperationalError) -> JSONResponse:
    # SIGNAL SQLSTATE '45000' inside a trigger arrives as MySQL error 1644 — a business rule, not a crash.
    if exc.args and exc.args[0] == 1644:
        return JSONResponse({"detail": exc.args[1]}, status_code=status.HTTP_409_CONFLICT)
    return JSONResponse({"detail": "Database is unavailable, try again"}, status_code=503)


# ---------- request bodies ----------

class OtpRequest(BaseModel):
    phone: Phone


class OtpVerify(BaseModel):
    phone: Phone
    otp: Annotated[str, Field(pattern=r"^\d{6}$")]


class BookingIn(BaseModel):
    meal_date: date
    slot_id: SlotId
    mess_id: MessId | None = None  # None = skip this meal


class PauseIn(BaseModel):
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def check_range(self) -> "PauseIn":
        if self.to_date < self.from_date:
            raise ValueError("Return date must be on or after the leaving date")
        return self


class ServeIn(BaseModel):
    phone: Phone
    mess_id: MessId
    slot_id: SlotId


class CloseIn(BaseModel):
    meal_date: date
    slot_id: SlotId


def _bad(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, msg)


# ---------- health ----------

@app.get("/health", tags=["system"])
def health(conn: Conn) -> dict[str, str]:
    repo.slot_exists(conn, 1)  # proves the database answers, not just the API
    return {"status": "ok", "today": str(today())}


# ---------- login ----------

@app.post("/auth/request-otp", tags=["login"])
def request_otp(body: OtpRequest, conn: Conn) -> dict[str, str]:
    code = auth.issue_otp(conn, body.phone)
    if settings.otp_mode == "dev":
        print(f"[OTP] {body.phone} -> {code}", flush=True)
        # TODO(debt): no SMS gateway yet (India needs DLT registration) — the page shows the code instead.
        return {"message": "OTP sent", "dev_otp": code}
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "SMS sending not set up yet")


@app.post("/auth/verify-otp", tags=["login"])
def verify_otp(body: OtpVerify, conn: Conn) -> dict[str, str]:
    student_id = auth.verify_otp(conn, body.phone, body.otp)
    return {"token": auth.make_token(student_id), "phone": body.phone}


# ---------- student ----------

@app.get("/menu", tags=["student"])
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


@app.get("/bookings/me", tags=["student"])
def my_bookings(student_id: StudentId, conn: Conn, meal_date: date | None = None) -> dict:
    d = meal_date or today()
    return {"meal_date": d, "paused": repo.is_paused(conn, student_id, d), "bookings": repo.bookings_for(conn, student_id, d)}


@app.post("/bookings", tags=["student"])
def book(body: BookingIn, student_id: StudentId, conn: Conn) -> dict[str, str]:
    t = today()
    if not t <= body.meal_date <= t + timedelta(days=settings.booking_days_ahead):
        raise _bad(f"Pick a date from today to {settings.booking_days_ahead} days ahead")
    if not repo.slot_exists(conn, body.slot_id) or (body.mess_id and not repo.mess_exists(conn, body.mess_id)):
        raise _bad("Unknown meal or mess")
    repo.upsert_booking(conn, student_id, body.meal_date, body.slot_id, body.mess_id)  # trigger blocks if paused
    return {"status": "booked" if body.mess_id else "skipped"}


@app.get("/pause/me", tags=["student"])
def my_pauses(student_id: StudentId, conn: Conn) -> dict:
    return {"pauses": repo.active_pauses(conn, student_id, today())}


@app.post("/pause", tags=["student"])
def pause(body: PauseIn, student_id: StudentId, conn: Conn) -> dict[str, str]:
    t = today()
    if body.from_date < t:
        raise _bad("You can't pause a day that has already passed")
    if (body.to_date - body.from_date).days >= settings.max_pause_days:
        raise _bad(f"A pause can be at most {settings.max_pause_days} days")
    repo.pause(conn, student_id, body.from_date, body.to_date)
    return {"status": "paused"}


@app.post("/resume", tags=["student"])
def resume(student_id: StudentId, conn: Conn) -> dict[str, str]:
    repo.resume(conn, student_id, today())
    return {"status": "resumed"}


# ---------- mess staff (PIN) ----------

@app.get("/staff/check", tags=["staff"])
def staff_check(_: Staff) -> dict[str, str]:
    return {"status": "ok"}


@app.post("/staff/serve", tags=["staff"])
def staff_serve(body: ServeIn, _: Staff, conn: Conn) -> dict:
    """Record that a student ate. Works for walk-ins too; they come out of the 30% buffer."""
    student = repo.student_by_phone(conn, body.phone)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No student with this number — they must log in once first")
    if not repo.slot_exists(conn, body.slot_id) or not repo.mess_exists(conn, body.mess_id):
        raise _bad("Unknown meal or mess")
    t = today()
    booking = repo.booking_at(conn, student["id"], t, body.slot_id)
    try:
        repo.serve(conn, student["id"], t, body.slot_id, body.mess_id)
    except pymysql.err.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already served this meal today") from None
    booked_here = bool(booking and booking["status"] == "booked" and booking["mess_id"] == body.mess_id)
    return {
        "served": True,
        "booked_here": booked_here,
        "booking": booking["mess"] if booking and booking["mess"] else (booking["status"] if booking else "none"),
    }


@app.post("/staff/close-meal", tags=["staff"])
def staff_close_meal(body: CloseIn, _: Staff, conn: Conn) -> dict:
    """Run sp_close_meal: leftover food is assigned to the NGO that has received the least so far."""
    repo.close_meal(conn, body.meal_date, body.slot_id)
    return {"donations": [d for d in repo.donations_on(conn, body.meal_date) if d["slot_id"] == body.slot_id]}


# ---------- public dashboards (no personal data) ----------

@app.get("/stats/today", tags=["dashboard"])
def stats_today(conn: Conn) -> dict:
    t = today()
    return {"meal_date": t, "forecast": repo.forecast(conn, t)}


_PHONE = re.compile(r"\b([6-9]\d)\d{5}(\d{3})\b")


@app.get("/admin/live", tags=["dashboard"])
def live(conn: Conn, limit: int = Query(default=25, ge=1, le=100)) -> dict:
    t = today()
    # Phones are masked because this endpoint is public.
    activity = [{**a, "detail": _PHONE.sub(r"\1xxxxx\2", a["detail"])} for a in repo.recent_activity(conn, limit)]
    return {
        "meal_date": t,
        "activity": activity,
        "summary": repo.meal_summary(conn, t),
        "donations": repo.donations_on(conn, t),
        "ngos": repo.ngo_totals(conn),
    }


@app.get("/admin", include_in_schema=False)
def admin_redirect() -> RedirectResponse:
    return RedirectResponse("/dashboard.html")


# The same site that GitHub Pages serves, so the whole system also runs offline from one laptop.
SITE = Path(__file__).resolve().parent.parent / "docs"
if SITE.is_dir():
    app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
