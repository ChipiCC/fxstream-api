"""ASGI middleware: request context/access logging, security headers, rate limiting.

All middleware here is **pure ASGI** rather than Starlette's ``BaseHTTPMiddleware``,
which avoids its known edge cases around streaming responses, background tasks
and context variables.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterable

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import get_logger

logger = get_logger(__name__)

# Paths that must never be rate limited (probes and metrics scrapers).
_RATE_LIMIT_EXEMPT: frozenset[str] = frozenset({"/health/live", "/health/ready"})


class RequestContextMiddleware:
    """Bind request metadata to the log context and emit an access log.

    Also echoes (or generates) an ``X-Request-ID`` header on the response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=scope["method"],
            path=scope["path"],
        )

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            structlog.contextvars.bind_contextvars(status_code=status_code)
            logger.info(
                "http_request",
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )


class SecurityHeadersMiddleware:
    """Attach conservative security headers to every response."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self._headers = {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "referrer-policy": "no-referrer",
            "permissions-policy": "geolocation=(), microphone=(), camera=()",
        }
        if hsts:
            self._headers["strict-transport-security"] = "max-age=63072000; includeSubDomains"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in self._headers.items():
                    headers.setdefault(key, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RateLimitMiddleware:
    """A per-client fixed-window rate limiter.

    In-memory and therefore per-process: it is a sensible default for a single
    worker or an extra guard, but a multi-worker/multi-replica deployment should
    front the service with a shared limiter (edge proxy, Redis, ...). See
    ``docs/security.md``.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_requests: int,
        window_seconds: int,
        exempt_paths: Iterable[str] = _RATE_LIMIT_EXEMPT,
    ) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exempt_paths = frozenset(exempt_paths)
        self._hits: dict[str, tuple[int, float]] = {}

    def _client_key(self, scope: Scope) -> str:
        client = scope.get("client")
        if client:
            return str(client[0])
        return "unknown"

    def _reject(self, scope: Scope, retry_after: int) -> tuple[bytes, list[tuple[bytes, bytes]]]:
        body = json.dumps(
            {
                "error": {
                    "code": "too_many_requests",
                    "message": "Rate limit exceeded",
                }
            }
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"retry-after", str(retry_after).encode()),
        ]
        return body, headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        key = self._client_key(scope)
        count, reset_at = self._hits.get(key, (0, now + self.window_seconds))
        if now >= reset_at:
            count, reset_at = 0, now + self.window_seconds
        count += 1
        self._hits[key] = (count, reset_at)

        if count > self.max_requests:
            body, headers = self._reject(scope, max(1, int(reset_at - now)))
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)
