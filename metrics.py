"""Prometheus metrics. No personal data is ever used as a label."""
import time

from flask import Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    generate_latest,
)


def init_metrics(app):
    registry = CollectorRegistry()
    started = time.time()

    requests_total = Counter(
        "careconnect_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    latency = Histogram(
        "careconnect_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
        registry=registry,
    )
    up = Gauge("careconnect_app_up", "1 when the application is running", registry=registry)
    uptime = Gauge("careconnect_uptime_seconds", "Seconds since application start", registry=registry)
    booked = Counter(
        "careconnect_appointments_booked_total", "Appointments booked (count only)", registry=registry
    )
    cancelled = Counter(
        "careconnect_appointments_cancelled_total", "Appointments cancelled (count only)", registry=registry
    )
    up.set(1)
    uptime.set_function(lambda: time.time() - started)
    ProcessCollector(registry=registry)  # CPU and memory of this process (Linux)

    app.extensions["metrics"] = {"booked": booked, "cancelled": cancelled}

    @app.before_request
    def _start_timer():
        g._metrics_start = time.perf_counter()

    @app.after_request
    def _record(response):
        if request.path != "/metrics":
            # url_rule is the route pattern (a fixed string), so unknown URLs
            # cannot create unlimited label values.
            endpoint = request.url_rule.rule if request.url_rule else "unmatched"
            requests_total.labels(request.method, endpoint, str(response.status_code)).inc()
            start = g.get("_metrics_start")
            if start is not None:
                latency.labels(request.method, endpoint).observe(time.perf_counter() - start)
        return response

    @app.route("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)
