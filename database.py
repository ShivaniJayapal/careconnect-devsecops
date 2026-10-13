"""SQLite helpers. Every query uses ? placeholders (parameterized queries)."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    email TEXT NOT NULL,
    doctor_id INTEGER NOT NULL,
    appointment_date TEXT NOT NULL,
    appointment_time TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Booked',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def add_appointment(conn, patient_name, email, doctor_id, date, time, reason) -> int:
    cur = conn.execute(
        "INSERT INTO appointments (patient_name, email, doctor_id, appointment_date, appointment_time, reason) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (patient_name, email, doctor_id, date, time, reason),
    )
    conn.commit()
    return cur.lastrowid


def slot_taken(conn, doctor_id, date, time) -> bool:
    row = conn.execute(
        "SELECT 1 FROM appointments WHERE doctor_id = ? AND appointment_date = ? "
        "AND appointment_time = ? AND status = 'Booked'",
        (doctor_id, date, time),
    ).fetchone()
    return row is not None


def list_appointments(conn) -> list:
    return conn.execute(
        "SELECT * FROM appointments ORDER BY appointment_date, appointment_time, id"
    ).fetchall()


def get_appointment(conn, appointment_id):
    return conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()


def cancel_appointment(conn, appointment_id) -> bool:
    cur = conn.execute(
        "UPDATE appointments SET status = 'Cancelled' WHERE id = ? AND status = 'Booked'",
        (appointment_id,),
    )
    conn.commit()
    return cur.rowcount == 1


def ping(conn) -> bool:
    return conn.execute("SELECT 1").fetchone()[0] == 1
