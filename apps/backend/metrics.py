"""Request count and latency for Prometheus."""

from __future__ import annotations

import os
import time

from flask import Flask, Response, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

REQUESTS = Counter(
    "skywatch_http_requests_total",
    "HTTP requests handled by this service.",
    ("method", "path", "status"),
)
LATENCY = Histogram(
    "skywatch_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ("method", "path"),
)


def install_metrics(app: Flask) -> None:
    @app.before_request
    def _start_timer() -> None:
        request.environ["skywatch_start"] = time.perf_counter()

    @app.after_request
    def _record(response: Response) -> Response:
        if request.path == "/metrics":
            return response
        path = request.url_rule.rule if request.url_rule is not None else "unmatched"
        elapsed = time.perf_counter() - float(request.environ.get("skywatch_start", time.perf_counter()))
        REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        LATENCY.labels(request.method, path).observe(elapsed)
        return response

    @app.get("/metrics")
    def metrics() -> Response:
        if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            payload = generate_latest(registry)
        else:
            payload = generate_latest()
        return Response(payload, mimetype=CONTENT_TYPE_LATEST)
