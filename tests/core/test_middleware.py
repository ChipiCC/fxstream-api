"""Tests for the request-context, security-header, and rate-limit middleware."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from core.middleware import RateLimitMiddleware


async def test_request_id_header_echoed(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"x-request-id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


async def test_request_id_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.headers.get("x-request-id")


async def test_security_headers_present(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


async def _ok(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _rate_limited_app(max_requests: int) -> Starlette:
    app = Starlette(routes=[Route("/x", _ok), Route("/health/live", _ok)])
    app.add_middleware(RateLimitMiddleware, max_requests=max_requests, window_seconds=60)
    return app


async def test_rate_limit_allows_up_to_threshold() -> None:
    transport = ASGITransport(app=_rate_limited_app(max_requests=2))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        assert (await client.get("/x")).status_code == 200
        assert (await client.get("/x")).status_code == 200


async def test_rate_limit_blocks_over_threshold() -> None:
    transport = ASGITransport(app=_rate_limited_app(max_requests=2))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.get("/x")
        await client.get("/x")

        response = await client.get("/x")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "too_many_requests"
        assert response.headers["retry-after"]


async def test_rate_limit_exempts_health() -> None:
    transport = ASGITransport(app=_rate_limited_app(max_requests=1))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        for _ in range(3):
            assert (await client.get("/health/live")).status_code == 200
