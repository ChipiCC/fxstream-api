"""Tests for the historical candles endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from candles.repository import CandleRepository
from market.models import Candle


async def _seed(session: AsyncSession, count: int = 3) -> list[Candle]:
    candles = [
        Candle(
            symbol="BTC/USDT",
            interval="1m",
            open_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=index),
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
        )
        for index in range(count)
    ]
    repository = CandleRepository(session)
    for candle in candles:
        await repository.upsert(candle)
    await session.commit()
    return candles


async def test_list_candles(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session, 3)
    response = await client.get(
        "/v1/rates/BTC/USDT/candles",
        params={"interval": "1m", "limit": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["open"] == "101"
    assert body[1]["open"] == "102"


async def test_unknown_symbol_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/v1/rates/DOGE/USD/candles")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_symbol"


async def test_invalid_interval_and_limit_are_rejected(client: AsyncClient) -> None:
    assert (
        await client.get("/v1/rates/BTC/USDT/candles", params={"interval": "5m"})
    ).status_code == 422
    assert (await client.get("/v1/rates/BTC/USDT/candles", params={"limit": 0})).status_code == 422
