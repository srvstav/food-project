import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing env var {name} — run db/setup.sh first")
    return value


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    token_secret: bytes
    otp_mode: Literal["dev", "sms"]
    allowed_origins: tuple[str, ...]
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_seconds: int = 30
    token_ttl_seconds: int = 7 * 24 * 3600
    booking_days_ahead: int = 7


def load_settings() -> Settings:
    mode = os.environ.get("OTP_MODE", "dev")
    if mode not in ("dev", "sms"):
        raise RuntimeError("OTP_MODE must be 'dev' or 'sms'")
    return Settings(
        db_host=os.environ.get("DB_HOST", "127.0.0.1"),
        db_port=int(os.environ.get("DB_PORT", "3306")),
        db_user=_required("DB_USER"),
        db_password=_required("DB_PASSWORD"),
        db_name=os.environ.get("DB_NAME", "mess"),
        token_secret=_required("TOKEN_SECRET").encode(),
        otp_mode=mode,  # type: ignore[arg-type]
        allowed_origins=tuple(o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()),
    )


settings = load_settings()
