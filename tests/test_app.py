import sqlite3
from datetime import date, timedelta

from tests.conftest import next_sunday, next_weekday


def test_homepage_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"CareConnect" in resp.data
    assert b"Dr. Ananya Rao" in resp.data


def test_all_pages_ok(client):
    for path in ("/book", "/appointments", "/about"):
        assert client.get(path).status_code == 200


def test_booking_with_valid_data(client, valid_form):
    resp = client.post("/book", data=valid_form, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Appointment confirmed" in resp.data


def test_booked_appointment_is_listed(client, valid_form):
    client.post("/book", data=valid_form)
    page = client.get("/appointments").data
    assert b"Test Patient" in page
    assert b"Dr. Ananya Rao" in page
    assert b"Booked" in page


def test_missing_patient_name_rejected(client, valid_form):
    valid_form["patient_name"] = ""
    resp = client.post("/book", data=valid_form)
    assert resp.status_code == 400
    assert b"Please enter the patient name" in resp.data
    assert b"Test Patient" not in client.get("/appointments").data


def test_invalid_doctor_rejected(client, valid_form):
    for bad in ("999", "abc", "", "1 OR 1=1"):
        valid_form["doctor_id"] = bad
        resp = client.post("/book", data=valid_form)
        assert resp.status_code == 400
        assert b"Please choose a doctor" in resp.data


def test_invalid_dates_rejected(client, valid_form):
    cases = {
        "not-a-date": b"valid date",
        (date.today() - timedelta(days=1)).isoformat(): b"cannot be in the past",
        (date.today() + timedelta(days=400)).isoformat(): b"up to 90 days",
        next_sunday().isoformat(): b"works",
        "": b"valid date",
    }
    for value, message in cases.items():
        valid_form["appointment_date"] = value
        resp = client.post("/book", data=valid_form)
        assert resp.status_code == 400, value
        assert message in resp.data, value


def test_invalid_time_rejected(client, valid_form):
    for bad in ("25:99", "03:00", "abc", ""):
        valid_form["appointment_time"] = bad
        assert client.post("/book", data=valid_form).status_code == 400


def test_invalid_email_rejected(client, valid_form):
    valid_form["email"] = "not-an-email"
    assert client.post("/book", data=valid_form).status_code == 400


def test_double_booking_rejected(client, valid_form):
    assert client.post("/book", data=valid_form).status_code == 302
    resp = client.post("/book", data=valid_form)
    assert resp.status_code == 400
    assert b"already booked" in resp.data


def test_cancel_via_post(client, valid_form):
    client.post("/book", data=valid_form)
    resp = client.post("/appointments/1/cancel", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Appointment cancelled" in resp.data
    assert b"Cancelled" in resp.data


def test_cancel_unknown_appointment_is_404(client):
    assert client.post("/appointments/999/cancel").status_code == 404


def test_unknown_route_returns_404(client):
    resp = client.get("/no-such-page")
    assert resp.status_code == 404
    assert b"could not find" in resp.data


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_metrics_endpoint(client):
    client.get("/")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "careconnect_http_requests_total" in body
    assert "careconnect_app_up 1.0" in body
    assert "careconnect_http_request_duration_seconds_bucket" in body


def test_invalid_input_does_not_crash(client):
    garbage = {
        "patient_name": "\x00" * 50,
        "email": "a" * 5000,
        "doctor_id": "💥",
        "appointment_date": "9999-99-99",
        "appointment_time": "%s%s%s",
        "reason": "x" * 5000,
    }
    assert client.post("/book", data=garbage).status_code in (400, 413)
    assert client.post("/book", data={}).status_code == 400
    assert client.get("/health").status_code == 200


def test_test_database_is_isolated(app, valid_form, tmp_path):
    app.test_client().post("/book", data=valid_form)
    assert (tmp_path / "test.db").exists()
    rows = sqlite3.connect(tmp_path / "test.db").execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    assert rows == 1


def test_booking_date_helper_is_weekday():
    assert next_weekday().weekday() < 5
