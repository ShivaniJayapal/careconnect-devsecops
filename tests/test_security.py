import re
import sqlite3
from pathlib import Path

import database
from tests.conftest import make_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_security_headers_present(client):
    resp = client.get("/")
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def test_csrf_blocks_post_without_token(tmp_path, valid_form):
    client = make_app(tmp_path, WTF_CSRF_ENABLED=True).test_client()
    resp = client.post("/book", data=valid_form)
    assert resp.status_code == 400
    assert b"expired or was invalid" in resp.data


def test_csrf_accepts_post_with_token(tmp_path, valid_form):
    client = make_app(tmp_path, WTF_CSRF_ENABLED=True).test_client()
    page = client.get("/book").data.decode()
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    valid_form["csrf_token"] = token
    assert client.post("/book", data=valid_form).status_code == 302


def test_cancel_requires_post(client, valid_form):
    client.post("/book", data=valid_form)
    assert client.get("/appointments/1/cancel").status_code == 405


def test_html_is_escaped(client, valid_form):
    valid_form["reason"] = "<script>alert(1)</script>"
    client.post("/book", data=valid_form)
    page = client.get("/appointments").data.decode()
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_500_page_hides_details(tmp_path):
    app = make_app(tmp_path, PROPAGATE_EXCEPTIONS=False)

    @app.route("/boom")
    def boom():
        raise RuntimeError("secret-internal-detail")

    resp = app.test_client().get("/boom")
    assert resp.status_code == 500
    assert b"secret-internal-detail" not in resp.data
    assert b"Traceback" not in resp.data
    assert b"went wrong" in resp.data


def test_database_layer_is_parameterized(tmp_path):
    db_path = tmp_path / "param.db"
    conn = database.connect(str(db_path))
    database.init_db(conn)
    nasty = "O'Brien\"); DROP TABLE appointments; --"
    database.add_appointment(conn, nasty, "x@example.com", 1, "2030-01-01", "10:00", nasty)
    stored = database.list_appointments(conn)
    assert len(stored) == 1
    assert stored[0]["patient_name"] == nasty  # stored literally, not executed
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "appointments" in tables
    assert database.get_appointment(conn, "1 OR 1=1") is None  # injection string matches nothing
    conn.close()


def test_no_string_built_sql_in_source():
    pattern = re.compile(r"execute(?:script|many)?\(\s*(?:f[\"']|[\"'][^\"']*[\"']\s*(?:%|\.format|\+))")
    offenders = []
    for name in ("app.py", "database.py", "scripts/seed_demo_data.py"):
        text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(name)
    assert offenders == []


def test_session_cookie_flags(client):
    from flask import current_app  # noqa: F401
    app = client.application
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
