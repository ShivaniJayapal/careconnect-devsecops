# CareConnect: Secure Healthcare Appointment Portal (DevSecOps demo)

A **fictional** patient appointment portal built for a college mini-project: *Secure DevOps (DevSecOps) Implementation in a Healthcare System*.
All doctors and patients are fictional. This is **not** a production medical records system. Never enter real personal or medical data.

Pipeline: GitHub -> Jenkins -> pytest -> Bandit -> Docker build -> Trivy -> Docker Hub -> Kubernetes (Minikube) -> verification, with Prometheus and Grafana monitoring.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest
python app.py          # opens on http://127.0.0.1:5000
```

If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again.

Optional sample data: `python scripts\seed_demo_data.py` (add `--reset` to wipe, `--reset --empty` for a clean database).
Reset by hand: stop the app and delete the `instance` folder.

## Configuration (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| SECRET_KEY | Signs sessions and CSRF tokens | random per process (set it in Kubernetes via a Secret) |
| DATABASE_PATH | SQLite file | instance/careconnect.db |
| DOCTORS_CSV | Doctor dataset | data/doctors.csv |
| COOKIE_SECURE | Set `true` only behind HTTPS | false |

## Endpoints

`/` home, `/book`, `/appointments`, `/about`, `/health` (JSON status), `/metrics` (Prometheus).

## Security gates

* Bandit fails the build on severity MEDIUM or higher with confidence MEDIUM or higher (`bandit -c bandit.yaml -r . -ll -ii`).
* Trivy fails the build on fixable HIGH or CRITICAL vulnerabilities in the built image; scanner errors also fail the build.
* Demo of a failing gate: copy `security_demo_fixture.py` from the guide into the project root, push, watch Jenkins stop at Bandit, then delete the file.
