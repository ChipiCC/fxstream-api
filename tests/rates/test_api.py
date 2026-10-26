"""Tests for the latest-rate snapshot endpoint."""

from __future__ import annotations

from httpx import AsyncClient

from market.runtime import MarketRuntime
from tests.helpers.fakes import make_tick


async def test_snapshot_returns_current_rates(client: AsyncClient, market: MarketRuntime) -> None:
    market.rate_store.update(make_tick(symbol="BTC/USDT", clock=market.clock))
    market.rate_store.update(make_tick(symbol="EUR/USD", source="frankfurter", clock=market.clock))

    response = await client.get("/v1/rates")
    assert response.status_code == 200
    body = response.json()
    assert [rate["symbol"] for rate in body] == ["BTC/USDT", "EUR/USD"]
    assert body[0]["price"] == "100.1"
    assert body[0]["stale"] is False


async def test_snapshot_filters_requested_symbols(
    client: AsyncClient, market: MarketRuntime
) -> None:
    market.rate_store.update(make_tick(symbol="BTC/USDT", clock=market.clock))
    market.rate_store.update(make_tick(symbol="EUR/USD", source="frankfurter", clock=market.clock))

    response = await client.get("/v1/rates", params={"symbols": "EUR/USD"})
    assert response.status_code == 200
    assert [rate["symbol"] for rate in response.json()] == ["EUR/USD"]


async def test_snapshot_rejects_unknown_symbol(client: AsyncClient) -> None:
    response = await client.get("/v1/rates", params={"symbols": "DOGE/USD"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_symbol"


async def test_snapshot_empty_before_ticks(client: AsyncClient) -> None:
    response = await client.get("/v1/rates")
    assert response.status_code == 200
    assert response.json() == []
