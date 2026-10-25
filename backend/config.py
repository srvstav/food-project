import base64
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# On Render every setting arrives packed in one value (made by setup_cloud.bat).
if packed := os.environ.get("MESS_SETTINGS"):
    for _k, _v in json.loads(base64.b64decode(packed)).items():
        os.environ.setdefault(_k, str(_v))

IST = ZoneInfo("Asia/Kolkata")  # cloud servers run on UTC; the mess runs on India time


def today() -> date:
    return datetime.now(IST).date()


def now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing env var {name}. Run setup first (setup.bat / python setup.py local).")
    return value


def _ssl_ca_path() -> str | None:
    """Cloud MySQL needs TLS. Accept a file path, or the PEM text itself (handy on Render)."""
    if path := os.environ.get("DB_SSL_CA"):
        return path
    if pem := os.environ.get("DB_SSL_CA_PEM"):
        f = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
        f.write(pem.replace("\\n", "\n"))
        f.close()
        return f.name
    return None


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_ssl_ca: str | None
    token_secret: bytes
    staff_pin: str
    otp_mode: Literal["dev", "sms"]
    allowed_origins: tuple[str, ...]
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_seconds: int = 30
    token_ttl_seconds: int = 7 * 24 * 3600
    booking_days_ahead: int = 7
    max_pause_days: int = 60


def load_settings() -> Settings:
    mode = os.environ.get("OTP_MODE", "dev")
    if mode not in ("dev", "sms"):
        raise RuntimeError("OTP_MODE must be 'dev' or 'sms'")
    pin = _required("STAFF_PIN")
    if len(pin) < 6:
        raise RuntimeError("STAFF_PIN must be at least 6 characters")
    return Settings(
        db_host=os.environ.get("DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("DB_PORT", "3306")),
        db_user=_required("DB_USER"),
        db_password=_required("DB_PASSWORD"),
        db_name=os.environ.get("DB_NAME", "mess"),
        db_ssl_ca=_ssl_ca_path(),
        token_secret=_required("TOKEN_SECRET").encode(),
        staff_pin=pin,
        otp_mode=mode,  # type: ignore[arg-type]
        allowed_origins=tuple(o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()),
    )


settings = load_settings()
