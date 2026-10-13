"""Doctor dataset loading and appointment slot helpers (fictional data only)."""
import csv
from datetime import datetime, timedelta
from pathlib import Path

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLOT_MINUTES = 30


def parse_days(spec: str) -> set:
    """Turn 'Mon-Fri' or 'Mon,Wed,Fri' into a set of weekday numbers (Mon=0)."""
    days = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = (p.strip() for p in part.split("-", 1))
            i, j = DAY_NAMES.index(start), DAY_NAMES.index(end)
            days.update(range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1)))
        else:
            days.add(DAY_NAMES.index(part))
    return days


def _slots(start: str, end: str) -> list:
    t = datetime.strptime(start, "%H:%M")
    stop = datetime.strptime(end, "%H:%M")
    out = []
    while t < stop:
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=SLOT_MINUTES)
    return out


def load_doctors(csv_path: str) -> list:
    path = Path(csv_path)
    if not path.is_file():
        raise RuntimeError(f"Doctor dataset not found: {csv_path}")
    doctors = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                doctors.append(
                    {
                        "id": int(row["id"]),
                        "name": row["name"].strip(),
                        "specialty": row["specialty"].strip(),
                        "working_days": row["working_days"].strip(),
                        "days": parse_days(row["working_days"]),
                        "start_time": row["start_time"].strip(),
                        "end_time": row["end_time"].strip(),
                        "slots": _slots(row["start_time"].strip(), row["end_time"].strip()),
                        "description": row["description"].strip(),
                    }
                )
            except (KeyError, ValueError) as exc:
                raise RuntimeError(f"Invalid row in doctor dataset: {row!r}") from exc
    if not doctors:
        raise RuntimeError("Doctor dataset is empty.")
    return doctors


def all_slots(doctors: list) -> list:
    return sorted({slot for d in doctors for slot in d["slots"]})
