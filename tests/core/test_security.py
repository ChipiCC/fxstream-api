"""Tests for API-key authentication."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from core.config import get_settings


@pytest.fixture
def api_key_enabled() -> Iterator[None]:
    """Configure a single API key for the duration of a test."""
    settings = get_settings()
    settings.api_keys = ["secret-key"]
    yield
    settings.api_keys = []


async def test_protected_route_requires_key(client: AsyncClient, api_key_enabled: None) -> None:
    response = await client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "ApiKey"


async def test_protected_route_accepts_valid_key(
    client: AsyncClient, api_key_enabled: None
) -> None:
    response = await client.get("/api/v1/items", headers={"X-API-Key": "secret-key"})
    assert response.status_code == 200


async def test_protected_route_rejects_invalid_key(
    client: AsyncClient, api_key_enabled: None
) -> None:
    response = await client.get("/api/v1/items", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


async def test_public_routes_stay_open(client: AsyncClient, api_key_enabled: None) -> None:
    assert (await client.get("/health/live")).status_code == 200


async def test_auth_is_disabled_when_no_keys_configured(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/items")).status_code == 200
