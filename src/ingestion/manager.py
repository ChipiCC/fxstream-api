"""Supervise provider tasks and route ticks to consumers."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from candles.aggregator import CandleAggregator
from core.logging import get_logger
from market.event_bus import EventBus
from market.models import Tick
from market.rate_store import RateStore
from providers.base import RateProvider

logger = get_logger(__name__)


class IngestionManager:
    """Start/stop ingestion and fan ticks into the cache, bus, and candles."""

    def __init__(
        self,
        *,
        rate_store: RateStore,
        event_bus: EventBus,
        providers: Sequence[RateProvider],
        aggregator: CandleAggregator | None = None,
    ) -> None:
        self._rate_store = rate_store
        self._event_bus = event_bus
        self._providers = list(providers)
        self._aggregator = aggregator
        self._tasks: list[asyncio.Task[None]] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._tasks.extend(
            asyncio.create_task(self._run_provider(provider), name=f"provider-{provider.name}")
            for provider in self._providers
        )
        if self._aggregator is not None:
            self._tasks.append(
                asyncio.create_task(self._aggregator.run(), name="candle-aggregator")
            )

    async def stop(self) -> None:
        await asyncio.gather(
            *(provider.stop() for provider in self._providers),
            return_exceptions=True,
        )
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._aggregator is not None:
            await self._aggregator.stop()
        self._started = False

    async def _run_provider(self, provider: RateProvider) -> None:
        try:
            await provider.run(self._on_tick)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("provider_task_crashed", provider=provider.name)

    def _on_tick(self, tick: Tick) -> None:
        self._rate_store.update(tick)
        self._event_bus.publish(tick)
        if self._aggregator is not None:
            self._aggregator.ingest(tick)
