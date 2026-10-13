"""Create the database and optionally load clearly fictional demo appointments.

Usage (from the project root):
    python scripts/seed_demo_data.py             # create tables, add sample rows if the table is empty
    python scripts/seed_demo_data.py --reset     # wipe all appointments, then add sample rows
    python scripts/seed_demo_data.py --reset --empty   # wipe all appointments, add nothing
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from config import Config  # noqa: E402

SAMPLE = [
    ("Test Patient One", "test.patient1@example.com", 1, 1, "10:00", "Routine check-up"),
    ("Test Patient Two", "test.patient2@example.com", 4, 2, "09:30", "Child vaccination visit"),
    ("Test Patient Three", "test.patient3@example.com", 3, 3, "11:00", "Skin consultation"),
    ("Test Patient Four", "test.patient4@example.com", 2, 4, "10:30", "Follow-up visit"),
    ("Test Patient Five", "test.patient5@example.com", 9, 5, "09:00", "Vision test"),
]


def next_weekday(start: date, offset: int) -> date:
    d = start + timedelta(days=offset)
    while d.weekday() > 4:  # all doctors work Mon-Fri at least
        d += timedelta(days=1)
    return d


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete all existing appointments first")
    parser.add_argument("--empty", action="store_true", help="do not add sample appointments")
    args = parser.parse_args()

    conn = database.connect(Config.DATABASE_PATH)
    database.init_db(conn)
    if args.reset:
        conn.execute("DELETE FROM appointments")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("appointments",))
        conn.commit()
        print("All appointments deleted.")
    count = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    if not args.empty and count == 0:
        today = date.today()
        for name, email, doctor_id, offset, time, reason in SAMPLE:
            database.add_appointment(conn, name, email, doctor_id, next_weekday(today, offset).isoformat(), time, reason)
        print(f"Added {len(SAMPLE)} fictional sample appointments.")
    print(f"Database ready at {Config.DATABASE_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
