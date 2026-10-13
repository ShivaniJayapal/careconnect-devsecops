"""Application configuration. All secrets come from environment variables."""
import logging
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    # No key supplied: generate a random one for this process only.
    # Nothing is hardcoded in the repository or the Docker image.
    logger.warning("SECRET_KEY is not set; using a random key for this process only.")
    return secrets.token_hex(32)


class Config:
    SECRET_KEY = _secret_key()
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "careconnect.db"))
    DOCTORS_CSV = os.environ.get("DOCTORS_CSV", str(BASE_DIR / "data" / "doctors.csv"))

    # Cookie hardening. COOKIE_SECURE must stay false for plain-HTTP local demos
    # and should be true behind HTTPS.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("COOKIE_SECURE", False)

    MAX_CONTENT_LENGTH = 16 * 1024  # forms are tiny; reject large bodies
    BOOKING_WINDOW_DAYS = 90
    JSON_SORT_KEYS = False
