"""Tests for 1-minute candle aggregation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from candles.aggregator import CandleAggregator
from market.models import Tick
from tests.helpers.fakes import FakeCandleWriter, FakeClock, make_tick

BASE = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _tick_at(minute: int, second: int, price: str) -> Tick:
    return make_tick(
        bid=price,
        ask=price,
        last=price,
        as_of=BASE + timedelta(minutes=minute, seconds=second),
    )


async def test_closed_bucket_is_flushed_and_current_is_held() -> None:
    writer = FakeCandleWriter()
    aggregator = CandleAggregator(
        writer=writer,
        clock=FakeClock(BASE + timedelta(minutes=1)),
    )

    aggregator.ingest(_tick_at(0, 1, "100"))
    aggregator.ingest(_tick_at(0, 30, "110"))
    aggregator.ingest(_tick_at(0, 50, "105"))
    aggregator.ingest(_tick_at(1, 1, "120"))

    await aggregator.flush()
    assert writer.calls == 1
    candle = writer.candles[0]
    assert candle.open == Decimal("100")
    assert candle.high == Decimal("110")
    assert candle.low == Decimal("100")
    assert candle.close == Decimal("105")
    assert candle.volume is None

    await aggregator.stop()
    assert len(writer.candles) == 2
    assert writer.candles[1].open == Decimal("120")


async def test_late_ticks_are_ignored() -> None:
    writer = FakeCandleWriter()
    aggregator = CandleAggregator(writer=writer)
    aggregator.ingest(_tick_at(1, 1, "100"))
    aggregator.ingest(_tick_at(0, 30, "999"))
    await aggregator.stop()

    assert writer.candles[0].open == Decimal("100")
    assert writer.candles[0].high == Decimal("100")


async def test_failed_flush_keeps_pending_candles() -> None:
    writer = FakeCandleWriter(fail=True)
    aggregator = CandleAggregator(writer=writer, clock=FakeClock(BASE + timedelta(minutes=1)))
    aggregator.ingest(_tick_at(0, 1, "100"))
    aggregator.ingest(_tick_at(1, 1, "110"))

    await aggregator.flush()
    assert aggregator.pending_count == 1

    writer.fail = False
    await aggregator.flush()
    assert aggregator.pending_count == 0
    assert len(writer.candles) == 1


async def test_flush_closes_expired_bucket_without_a_new_tick() -> None:
    clock = FakeClock(BASE)
    writer = FakeCandleWriter()
    aggregator = CandleAggregator(writer=writer, clock=clock)
    aggregator.ingest(_tick_at(0, 1, "100"))

    await aggregator.flush()
    assert writer.candles == []

    clock.advance(60)
    await aggregator.flush()
    assert len(writer.candles) == 1
    assert writer.candles[0].close == Decimal("100")


async def test_late_tick_after_flush_cannot_rewrite_closed_candle() -> None:
    clock = FakeClock(BASE)
    writer = FakeCandleWriter()
    aggregator = CandleAggregator(writer=writer, clock=clock)
    aggregator.ingest(_tick_at(0, 1, "100"))

    clock.advance(60)
    await aggregator.flush()
    assert len(writer.candles) == 1

    aggregator.ingest(_tick_at(0, 30, "999"))
    await aggregator.flush()
    assert len(writer.candles) == 1
    assert writer.candles[0].close == Decimal("100")


async def test_run_loop_flushes_periodically() -> None:
    writer = FakeCandleWriter()
    aggregator = CandleAggregator(writer=writer, flush_seconds=1)
    task = asyncio.create_task(aggregator.run())
    aggregator.ingest(_tick_at(0, 1, "100"))
    aggregator.ingest(_tick_at(1, 1, "110"))
    await asyncio.sleep(0)
    await aggregator.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
