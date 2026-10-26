"""Tests for the ingestion supervisor."""

from __future__ import annotations

import asyncio

from candles.aggregator import CandleAggregator
from ingestion.manager import IngestionManager
from market.event_bus import EventBus
from market.models import ProviderState, ProviderStatus
from market.rate_store import RateStore
from providers.base import RateProvider, TickSink
from tests.helpers.fakes import FakeCandleWriter, FakeClock, FakeProvider, make_tick


def _manager(
    providers: list[RateProvider],
    *,
    aggregator: CandleAggregator | None = None,
) -> tuple[IngestionManager, RateStore, EventBus]:
    clock = FakeClock()
    rate_store = RateStore(clock=clock, stale_seconds={"binance": 10})
    event_bus = EventBus()
    manager = IngestionManager(
        rate_store=rate_store,
        event_bus=event_bus,
        providers=providers,
        aggregator=aggregator,
    )
    return manager, rate_store, event_bus


async def test_manager_routes_ticks_to_store_bus_and_aggregator() -> None:
    writer = FakeCandleWriter()
    aggregator = CandleAggregator(writer=writer)
    manager, rate_store, event_bus = _manager(
        [FakeProvider([make_tick(clock=FakeClock())])],
        aggregator=aggregator,
    )
    subscription = event_bus.subscribe(["BTC/USDT"])
    try:
        await manager.start()
        await asyncio.sleep(0)
        assert rate_store.get("BTC/USDT") is not None
        assert (await subscription.wait())["BTC/USDT"].symbol == "BTC/USDT"
        await manager.stop()
        assert len(writer.candles) == 1
    finally:
        subscription.close()
        event_bus.unsubscribe(subscription)


async def test_provider_crash_does_not_stop_other_providers() -> None:
    class CrashingProvider(RateProvider):
        name = "crashing"

        async def run(self, sink: TickSink) -> None:
            raise RuntimeError("boom")

        async def stop(self) -> None:
            return None

        def status(self) -> ProviderStatus:
            return ProviderStatus(name=self.name, state=ProviderState.DOWN)

    good = FakeProvider([make_tick(symbol="ETH/USDT", bid="10", ask="12", clock=FakeClock())])
    manager, rate_store, _event_bus = _manager([CrashingProvider(), good])
    try:
        await manager.start()
        await asyncio.sleep(0.01)
        assert rate_store.get("ETH/USDT") is not None
    finally:
        await manager.stop()


async def test_stop_before_start_is_safe() -> None:
    manager, _rate_store, _event_bus = _manager([])
    await manager.stop()
