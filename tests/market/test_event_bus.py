"""Tests for the coalescing event bus."""

from __future__ import annotations

import asyncio

import pytest

from market.event_bus import EventBus
from tests.helpers.fakes import make_tick


async def test_publish_only_matching_symbols() -> None:
    bus = EventBus()
    subscription = bus.subscribe(["BTC/USDT"])
    try:
        assert bus.publish(make_tick(symbol="ETH/USDT")) == 0
        assert bus.publish(make_tick(symbol="BTC/USDT", bid="100", ask="102")) == 1
        ticks = await subscription.wait()
        assert set(ticks) == {"BTC/USDT"}
        assert ticks["BTC/USDT"].bid == 100
    finally:
        subscription.close()
        bus.unsubscribe(subscription)


async def test_slow_subscriber_keeps_latest_per_symbol() -> None:
    bus = EventBus()
    subscription = bus.subscribe(["BTC/USDT", "ETH/USDT"])
    try:
        bus.publish(make_tick(symbol="BTC/USDT", bid="100", ask="102"))
        bus.publish(make_tick(symbol="BTC/USDT", bid="200", ask="202"))
        bus.publish(make_tick(symbol="ETH/USDT", bid="10", ask="12"))
        bus.publish(make_tick(symbol="ETH/USDT", bid="20", ask="22"))

        ticks = await subscription.wait()
        assert ticks["BTC/USDT"].bid == 200
        assert ticks["ETH/USDT"].bid == 20
    finally:
        subscription.close()
        bus.unsubscribe(subscription)


async def test_subscribe_unsubscribe_and_close() -> None:
    bus = EventBus()
    subscription = bus.subscribe(["BTC/USDT"])
    assert bus.subscriber_count == 1
    assert subscription.offer(make_tick()) is True

    subscription.remove_symbols(["BTC/USDT"])
    assert subscription.symbols == frozenset()
    assert subscription.offer(make_tick()) is False

    subscription.add_symbols(["BTC/USDT"])
    subscription.close()
    assert subscription.closed is True
    assert subscription.offer(make_tick()) is False

    bus.unsubscribe(subscription)
    assert bus.subscriber_count == 0


async def test_wait_can_be_cancelled() -> None:
    bus = EventBus()
    subscription = bus.subscribe(["BTC/USDT"])
    task = asyncio.create_task(subscription.wait())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    subscription.close()
