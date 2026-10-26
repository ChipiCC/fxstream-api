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

PROVIDER_MESSAGES = Counter(
    "fxstream_provider_messages_total",
    "Normalized ticks received from a provider.",
    ["provider"],
)
PROVIDER_ERRORS = Counter(
    "fxstream_provider_errors_total",
    "Provider-level errors.",
    ["provider", "kind"],
)
PROVIDER_RECONNECTS = Counter(
    "fxstream_provider_reconnects_total",
    "Provider reconnection attempts.",
    ["provider"],
)
PROVIDER_STATE = Gauge(
    "fxstream_provider_state",
    "Provider state (down=0, degraded=1, up=2).",
    ["provider"],
)
PROVIDER_LAST_MESSAGE = Gauge(
    "fxstream_provider_last_message_timestamp_seconds",
    "Unix timestamp of the last provider message.",
    ["provider"],
)
WS_SUBSCRIBERS = Gauge(
    "fxstream_ws_subscribers",
    "Active WebSocket rate subscribers.",
)
WS_MESSAGES = Counter(
    "fxstream_ws_messages_total",
    "WebSocket outbound messages by outcome.",
    ["outcome"],
)
QUOTE_REQUESTS = Counter(
    "fxstream_quote_requests_total",
    "Quote requests by outcome.",
    ["outcome"],
)
QUOTE_DURATION = Histogram(
    "fxstream_quote_duration_seconds",
    "Quote generation latency in seconds.",
)

APP_INFO.labels(version=__version__).set(1)


def route_label(scope: Scope) -> str:
    """Return a low-cardinality route label.

    Uses the matched route template (``/quotes/{quote_id}``) and re-attaches the
    include prefix (``/v1``) so path parameters never explode label
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
