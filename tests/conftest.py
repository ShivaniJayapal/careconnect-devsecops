import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402


def next_weekday(offset: int = 1) -> date:
    """A date at least `offset` days ahead that falls Monday-Friday (all doctors work then)."""
    d = date.today() + timedelta(days=offset)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def next_sunday() -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d


def make_app(tmp_path, **overrides):
    cfg = {
        "TESTING": True,
        "SECRET_KEY": "test-only-secret",
        "DATABASE_PATH": str(tmp_path / "test.db"),  # isolated temporary database
        "WTF_CSRF_ENABLED": False,
    }
    cfg.update(overrides)
    return create_app(cfg)


@pytest.fixture
def app(tmp_path):
    return make_app(tmp_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def valid_form():
    return {
        "patient_name": "Test Patient",
        "email": "test.patient@example.com",
        "doctor_id": "1",
        "appointment_date": next_weekday().isoformat(),
        "appointment_time": "10:00",
        "reason": "Routine check-up",
    }
