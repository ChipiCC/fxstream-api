"""Aggregate ticks into 1-minute OHLC candles."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from core.clock import Clock, SystemClock
from core.logging import get_logger
from market.models import Candle, Tick

logger = get_logger(__name__)

Sleep = Callable[[float], Awaitable[None]]


class CandleWriterProtocol(Protocol):
    async def write(self, candles: Sequence[Candle]) -> None: ...


@dataclass(slots=True)
class _Builder:
    symbol: str
    open_time: datetime
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None

    def update(self, tick: Tick) -> None:
        price = tick.last
        if self.open is None:
            self.open = self.high = self.low = self.close = price
            return
        if self.high is None or self.low is None:
            self.high = self.low = price
        else:
            self.high = max(self.high, price)
            self.low = min(self.low, price)
        self.close = price

    def build(self) -> Candle:
        if self.open is None or self.high is None or self.low is None or self.close is None:
            raise ValueError("cannot build an empty candle")
        return Candle(
            symbol=self.symbol,
            interval="1m",
            open_time=self.open_time,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=None,
        )


class CandleAggregator:
    """Build candles from ticks and flush closed buckets in the background."""

    def __init__(
        self,
        *,
        writer: CandleWriterProtocol,
        clock: Clock | None = None,
        flush_seconds: int = 60,
        sleep: Sleep | None = None,
    ) -> None:
        self._writer = writer
        self._clock = clock or SystemClock()
        self._flush_seconds = flush_seconds
        self._sleep = sleep or asyncio.sleep
        self._current: dict[str, _Builder] = {}
        self._last_closed: dict[str, datetime] = {}
        self._pending: list[Candle] = []
        self._stop = asyncio.Event()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def ingest(self, tick: Tick) -> None:
        if self._stop.is_set():
            return
        bucket = tick.as_of.replace(second=0, microsecond=0)
        last_closed = self._last_closed.get(tick.symbol)
        if last_closed is not None and bucket <= last_closed:
            return
        builder = self._current.get(tick.symbol)
        if builder is None or bucket > builder.open_time:
            if builder is not None:
                self._pending.append(builder.build())
                self._last_closed[tick.symbol] = builder.open_time
            builder = _Builder(symbol=tick.symbol, open_time=bucket)
            self._current[tick.symbol] = builder
        elif bucket < builder.open_time:
            return
        builder.update(tick)

    async def flush(self) -> None:
        self._close_expired()
        if not self._pending:
            return
        batch, self._pending = self._pending, []
        try:
            await self._writer.write(batch)
        except Exception as exc:
            self._pending = [*batch, *self._pending]
            logger.warning("candle_flush_failed", count=len(batch), error=str(exc))

    async def run(self) -> None:
        while not self._stop.is_set():
            await self._sleep(float(self._flush_seconds))
            await self.flush()

    async def stop(self) -> None:
        self._stop.set()
        for builder in self._current.values():
            self._pending.append(builder.build())
        self._current.clear()
        await self.flush()

    def _close_expired(self) -> None:
        now = self._clock.now()
        for symbol, builder in list(self._current.items()):
            if builder.open_time + timedelta(minutes=1) <= now:
                self._pending.append(builder.build())
                self._last_closed[symbol] = builder.open_time
                del self._current[symbol]
