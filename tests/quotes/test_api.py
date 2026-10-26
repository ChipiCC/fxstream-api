"""Tests for quote REST endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from market.runtime import MarketRuntime
from tests.helpers.fakes import make_tick


async def test_create_and_fetch_quote(client: AsyncClient, market: MarketRuntime) -> None:
    market.rate_store.update(make_tick(bid="100", ask="100.2", clock=market.clock))

    response = await client.post(
        "/v1/quotes",
        json={"symbol": "BTC/USDT", "side": "buy", "amount": "0.5"},
    )
    assert response.status_code == 201
    quote = response.json()
    assert quote["symbol"] == "BTC/USDT"
    assert quote["side"] == "buy"
    assert quote["price"] == "100.15005"
    assert quote["bid"] == "100.04995"
    assert quote["ask"] == "100.15005"
    assert quote["amount"] == "0.5"
    assert quote["expires_at"] > quote["issued_at"]

    fetched = await client.get(f"/v1/quotes/{quote['quote_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["valid"] is True


async def test_quote_rejects_stale_rate(client: AsyncClient, market: MarketRuntime) -> None:
    market.rate_store.update(make_tick(as_of=datetime(2020, 1, 1, tzinfo=UTC), clock=market.clock))
    response = await client.post(
        "/v1/quotes",
        json={"symbol": "BTC/USDT", "side": "buy"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_rate"


async def test_quote_rejects_missing_rate(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/quotes",
        json={"symbol": "BTC/USDT", "side": "buy"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "rate_unavailable"


async def test_quote_validation_errors(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/quotes",
        json={"symbol": "BTC/USDT", "side": "hold"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    response = await client.post(
        "/v1/quotes",
        json={"symbol": "BTC/USDT", "side": "buy", "amount": "0"},
    )
    assert response.status_code == 422


async def test_get_missing_quote(client: AsyncClient) -> None:
    response = await client.get(f"/v1/quotes/{uuid.uuid4()}")
    assert response.status_code == 404
