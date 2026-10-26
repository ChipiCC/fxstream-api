"""Tests for candle persistence and retrieval against PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from candles.repository import CandleRepository
from candles.writer import CandleWriter
from market.models import Candle


def _candle(*, close: str = "101", open_time: datetime | None = None) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        interval="1m",
        open_time=open_time or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=None,
    )


async def test_upsert_and_list_are_ordered(session: AsyncSession) -> None:
    repository = CandleRepository(session)
    first = _candle()
    second = _candle(
        close="105",
        open_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    await repository.upsert(first)
    await repository.upsert(second)
    await session.commit()

    candles = await repository.list(symbol="BTC/USDT", interval="1m", limit=10)
    assert [candle.open_time for candle in candles] == [first.open_time, second.open_time]
    assert candles[1].close == Decimal("105")


async def test_upsert_is_idempotent(session: AsyncSession) -> None:
    repository = CandleRepository(session)
    await repository.upsert(_candle())
    await repository.upsert(_candle(close="103"))
    await session.commit()

    candles = await repository.list(symbol="BTC/USDT", interval="1m", limit=10)
    assert len(candles) == 1
    assert candles[0].close == Decimal("103")


async def test_writer_owns_its_session(engine: AsyncEngine) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    writer = CandleWriter(session_factory=factory)
    await writer.write([_candle()])
    await writer.write([])

    async with factory() as check_session:
        candles = await CandleRepository(check_session).list(
            symbol="BTC/USDT",
            interval="1m",
            limit=10,
        )
    assert len(candles) == 1
