"""Shared test doubles for clocks, providers, and candle writers."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from core.clock import Clock
from market.models import Candle, ProviderState, ProviderStatus, Tick
from providers.base import RateProvider, TickSink


class FakeClock:
    """Deterministic clock for expiry and staleness tests."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def make_tick(
    *,
    symbol: str = "BTC/USDT",
    bid: str = "100.00",
    ask: str = "100.20",
    last: str | None = None,
    source: str = "binance",
    as_of: datetime | None = None,
    received_at: datetime | None = None,
    clock: Clock | None = None,
) -> Tick:
    now = clock.now() if clock is not None else datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    bid_value = Decimal(bid)
    ask_value = Decimal(ask)
    return Tick(
        symbol=symbol,
        bid=bid_value,
        ask=ask_value,
        last=Decimal(last) if last is not None else (bid_value + ask_value) / 2,
        source=source,
        as_of=as_of or now,
        received_at=received_at or now,
    )


class FakeProvider(RateProvider):
    """Provider that emits a fixed list of ticks and optionally blocks."""

    name = "fake"

    def __init__(self, ticks: Sequence[Tick] = (), *, block: bool = False) -> None:
        self.ticks = list(ticks)
        self.block = block
        self.stopped = asyncio.Event()
        self.failures: list[Exception] = []
        self.started = False

    async def run(self, sink: TickSink) -> None:
        self.started = True
        for tick in self.ticks:
            sink(tick)
        if self.block:
            await self.stopped.wait()

    async def stop(self) -> None:
        self.stopped.set()

    def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, state=ProviderState.UP, reconnects=0)

    def fail(self, exc: Exception) -> None:
        self.failures.append(exc)


class FakeCandleWriter:
    """Record flushed candles and optionally fail the next write."""

    def __init__(self, fail: bool = False) -> None:
        self.candles: list[Candle] = []
        self.fail = fail
        self.calls = 0

    async def write(self, candles: Sequence[Candle]) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("candle store unavailable")
        self.candles.extend(candles)
