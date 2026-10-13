"""CareConnect - fictional patient appointment portal (educational DevSecOps demo)."""
import re
from datetime import date, datetime, timedelta

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import HTTPException

import database
from config import Config
from doctors import all_slots, load_doctors
from metrics import init_metrics

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,79}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
MAX_REASON = 200


def validate_booking(form, doctors_by_id, today=None):
    """Return (clean_data, errors). Never trusts client-side checks."""
    today = today or date.today()
    errors = {}

    name = " ".join(form.get("patient_name", "").split())
    if not name:
        errors["patient_name"] = "Please enter the patient name."
    elif not NAME_RE.match(name):
        errors["patient_name"] = "Use 2-80 letters; spaces, . ' and - are allowed."

    email = form.get("email", "").strip()
    if not email:
        errors["email"] = "Please enter an email address."
    elif not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address (use a fictional one)."

    doctor = None
    raw_doctor = form.get("doctor_id", "").strip()
    if raw_doctor.isdigit() and int(raw_doctor) in doctors_by_id:
        doctor = doctors_by_id[int(raw_doctor)]
    else:
        errors["doctor_id"] = "Please choose a doctor from the list."

    appt_date = None
    raw_date = form.get("appointment_date", "").strip()
    try:
        appt_date = date.fromisoformat(raw_date)
    except ValueError:
        errors["appointment_date"] = "Please choose a valid date."
    if appt_date is not None:
        latest = today + timedelta(days=Config.BOOKING_WINDOW_DAYS)
        if appt_date < today:
            errors["appointment_date"] = "The date cannot be in the past."
        elif appt_date > latest:
            errors["appointment_date"] = f"Appointments can be booked up to {Config.BOOKING_WINDOW_DAYS} days ahead."
        elif doctor and appt_date.weekday() not in doctor["days"]:
            errors["appointment_date"] = f"{doctor['name']} works {doctor['working_days']}."

    raw_time = form.get("appointment_time", "").strip()
    try:
        datetime.strptime(raw_time, "%H:%M")
        time_ok = True
    except ValueError:
        time_ok = False
    if not time_ok:
        errors["appointment_time"] = "Please choose a valid time."
    elif doctor and raw_time not in doctor["slots"]:
        errors["appointment_time"] = (
            f"{doctor['name']} is available {doctor['start_time']}-{doctor['end_time']} in 30-minute slots."
        )

    reason = " ".join(form.get("reason", "").split())
    if len(reason) > MAX_REASON:
        errors["reason"] = f"Please keep the reason under {MAX_REASON} characters."

    clean = {
        "patient_name": name,
        "email": email,
        "doctor": doctor,
        "date": appt_date.isoformat() if appt_date else "",
        "time": raw_time,
        "reason": reason,
    }
    return clean, errors


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.config["DOCTORS"] = load_doctors(app.config["DOCTORS_CSV"])
    doctors_by_id = {d["id"]: d for d in app.config["DOCTORS"]}
    time_options = all_slots(app.config["DOCTORS"])

    with database.connect(app.config["DATABASE_PATH"]) as conn:
        database.init_db(conn)
    app.teardown_appcontext(database.close_db)

    CSRFProtect(app)
    init_metrics(app)

    # ---------- security headers ----------
    @app.after_request
    def security_headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if request.is_secure:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- pages ----------
    @app.route("/")
    def index():
        return render_template("index.html", doctors=app.config["DOCTORS"])

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/book", methods=["GET", "POST"])
    def book_appointment():
        today = date.today()
        ctx = {
            "doctors": app.config["DOCTORS"],
            "time_options": time_options,
            "min_date": today.isoformat(),
            "max_date": (today + timedelta(days=Config.BOOKING_WINDOW_DAYS)).isoformat(),
            "form": {},
            "errors": {},
        }
        if request.method == "GET":
            ctx["form"] = {"doctor_id": request.args.get("doctor", "")}
            return render_template("book_appointment.html", **ctx)

        clean, errors = validate_booking(request.form, doctors_by_id, today)
        db = database.get_db()
        if not errors and database.slot_taken(db, clean["doctor"]["id"], clean["date"], clean["time"]):
            errors["appointment_time"] = "That slot is already booked. Please pick another time."
        if errors:
            ctx.update(form=request.form, errors=errors)
            return render_template("book_appointment.html", **ctx), 400

        database.add_appointment(
            db, clean["patient_name"], clean["email"], clean["doctor"]["id"],
            clean["date"], clean["time"], clean["reason"],
        )
        app.extensions["metrics"]["booked"].inc()
        flash(
            f"Appointment confirmed with {clean['doctor']['name']} on {clean['date']} at {clean['time']}.",
            "success",
        )
        return redirect(url_for("appointments"))

    @app.route("/appointments")
    def appointments():
        rows = database.list_appointments(database.get_db())
        items = [
            {**dict(r), "doctor_name": doctors_by_id.get(r["doctor_id"], {}).get("name", "Unknown doctor")}
            for r in rows
        ]
        return render_template("appointments.html", appointments=items)

    @app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
    def cancel(appointment_id):
        db = database.get_db()
        if database.get_appointment(db, appointment_id) is None:
            abort(404)
        if database.cancel_appointment(db, appointment_id):
            app.extensions["metrics"]["cancelled"].inc()
            flash("Appointment cancelled.", "success")
        else:
            flash("That appointment was already cancelled.", "info")
        return redirect(url_for("appointments"))

    @app.route("/health")
    def health():
        try:
            database.ping(database.get_db())
        except Exception:  # noqa: BLE001 - health must never raise
            return jsonify(status="error"), 503
        return jsonify(status="ok")

    # ---------- error handling (no stack traces to users) ----------
    @app.errorhandler(CSRFError)
    def csrf_error(_err):
        return render_template("error.html", code=400,
                               message="Your form expired or was invalid. Please go back and try again."), 400

    @app.errorhandler(404)
    def not_found(_err):
        return render_template("404.html"), 404

    @app.errorhandler(HTTPException)
    def http_error(err):
        return render_template("error.html", code=err.code, message=err.name), err.code

    @app.errorhandler(Exception)
    def server_error(err):
        app.logger.exception("Unhandled error: %s", type(err).__name__)
        return render_template("500.html"), 500

    return app


if __name__ == "__main__":
    # Local development only; production uses Gunicorn (see wsgi.py / Dockerfile).
    create_app().run(host="127.0.0.1", port=5000, debug=False)
