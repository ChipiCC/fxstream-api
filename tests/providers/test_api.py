"""Tests for the provider status endpoint."""

from __future__ import annotations

from httpx import AsyncClient

from market.runtime import MarketRuntime
from providers.registry import ProviderRegistry
from tests.helpers.fakes import FakeProvider


async def test_provider_status(client: AsyncClient, market: MarketRuntime) -> None:
    market.registry = ProviderRegistry([FakeProvider()])
    response = await client.get("/v1/providers/status")
    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "fake",
            "state": "up",
            "last_message_at": None,
            "reconnects": 0,
        }
    ]
