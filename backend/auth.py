"""OTP issue/verify and a small HMAC-signed bearer token (stdlib only)."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta

from fastapi import Header, HTTPException, status
from pymysql.connections import Connection

import repo
from config import now, settings


def _hash_code(phone: str, code: str) -> str:
    # Keyed hash so a leaked otp_codes table can't be brute-forced offline (only 10^6 codes).
    return hmac.new(settings.token_secret, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_otp(conn: Connection, phone: str) -> str:
    last = repo.latest_otp(conn, phone)
    t = now()
    if last and (t - last["created_at"]).total_seconds() < settings.otp_resend_seconds:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Wait a few seconds before asking for a new OTP")
    code = f"{secrets.randbelow(10**6):06d}"
    repo.insert_otp(conn, phone, _hash_code(phone, code), t, t + timedelta(seconds=settings.otp_ttl_seconds))
    return code


def verify_otp(conn: Connection, phone: str, code: str) -> int:
    otp = repo.latest_otp(conn, phone)
    if otp is None or otp["used_at"] is not None or otp["expires_at"] < now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OTP expired — request a new one")
    if otp["attempts"] >= settings.otp_max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries — request a new OTP")
    if not hmac.compare_digest(otp["code_hash"], _hash_code(phone, code)):
        repo.bump_otp_attempts(conn, otp["id"])
        conn.commit()  # keep the failed attempt even though we raise
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Wrong OTP")
    repo.mark_otp_used(conn, otp["id"])
    return repo.login_student(conn, phone)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(student_id: int) -> str:
    body = _b64(json.dumps({"sid": student_id, "exp": int(time.time()) + settings.token_ttl_seconds}).encode())
    sig = _b64(hmac.new(settings.token_secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def current_student(authorization: str = Header(default="")) -> int:
    """FastAPI dependency: returns student_id from 'Authorization: Bearer <token>'."""
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in again")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or "." not in token:
        raise unauthorized
    body, sig = token.rsplit(".", 1)
    expected = _b64(hmac.new(settings.token_secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise unauthorized
    try:
        payload = json.loads(_unb64(body))
    except ValueError:
        raise unauthorized from None
    if payload.get("exp", 0) < time.time():
        raise unauthorized
    return int(payload["sid"])


def staff_only(x_staff_pin: str = Header(default="")) -> None:
    """FastAPI dependency for mess-counter actions: 'X-Staff-Pin: <pin>'."""
    if not x_staff_pin or not hmac.compare_digest(x_staff_pin.encode(), settings.staff_pin.encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong staff PIN")
