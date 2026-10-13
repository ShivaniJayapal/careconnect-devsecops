# syntax=docker/dockerfile:1
# ---------- Stage 1: build dependencies ----------
FROM python:3.12.11-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---------- Stage 2: runtime image ----------
FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/instance/careconnect.db \
    PORT=8000

# Pick up Debian security fixes released after the base image was built,
# then remove pip (not needed at runtime) to shrink the attack surface.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && pip uninstall -y pip \
    && groupadd --system --gid 10001 careconnect \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin careconnect

COPY --from=builder /install /usr/local

WORKDIR /app
# Only the files the application needs (no tests, no .git, no secrets).
COPY app.py config.py database.py doctors.py metrics.py wsgi.py ./
COPY data ./data
COPY templates ./templates
COPY static ./static
RUN mkdir -p /app/instance && chown -R 10001:10001 /app/instance

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]

# One worker with threads keeps Prometheus counters in a single process.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "--access-logfile", "-", "wsgi:app"]
