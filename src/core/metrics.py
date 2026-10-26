"""Prometheus metrics: instrumentation middleware and the scrape endpoint."""

from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.version import __version__

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "route", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
)
APP_INFO = Gauge("app_info", "Application metadata.", ["version"])

APP_INFO.labels(version=__version__).set(1)


def route_label(scope: Scope) -> str:
    """Return a low-cardinality route label.

    Uses the matched route template (``/items/{item_id}``) and re-attaches the
    include prefix (``/api/v1``) so path parameters never explode label
    cardinality. Falls back to ``unmatched`` for 404s.
    """
    route = scope.get("route")
    template = getattr(route, "path", None)
    if not isinstance(template, str) or not template:
        return "unmatched"

    actual = scope.get("path")
    if not isinstance(actual, str):
        return template

    relative = [part for part in template.split("/") if part]
    if not relative:
        return template

    actual_segments = actual.split("/")
    prefix = actual_segments[: -len(relative)] if len(actual_segments) > len(relative) else []
    return f"{'/'.join(prefix)}{template}"


class MetricsMiddleware:
    """Record request counts and latency for the scrape endpoint."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = route_label(scope)
            REQUEST_COUNT.labels(method=method, route=route, status_code=str(status_code)).inc()
            REQUEST_DURATION.labels(method=method, route=route).observe(time.perf_counter() - start)


async def metrics_endpoint() -> Response:
    """Render the Prometheus exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
