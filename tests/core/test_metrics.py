"""Tests for Prometheus metrics instrumentation and the scrape endpoint."""

from __future__ import annotations

from httpx import AsyncClient


async def test_metrics_endpoint_exposes_prometheus(client: AsyncClient) -> None:
    await client.get("/health/live")

    response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "app_info" in body


async def test_metrics_records_route_template(client: AsyncClient) -> None:
    await client.get("/api/v1/items")

    body = (await client.get("/metrics")).text
    # path parameters must be collapsed to the route template, not the raw path
    assert 'route="/api/v1/items"' in body
