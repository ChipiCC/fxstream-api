"""Non-blocking in-process pub/sub for normalized ticks."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from core.symbols import normalize_symbol
from market.models import Tick


class Subscription:
    """A coalescing tick buffer for one WebSocket client.

    Offers never await. If the consumer is slow, newer ticks for the same symbol
    replace older ones; the next drain always contains at most one tick per pair.
    """

    def __init__(self, symbols: Iterable[str] | None = None) -> None:
        self._symbols = {normalize_symbol(symbol) for symbol in symbols or ()}
        self._latest: dict[str, Tick] = {}
        self._event = asyncio.Event()
        self._closed = False

    @property
    def symbols(self) -> frozenset[str]:
        return frozenset(self._symbols)

    @property
    def closed(self) -> bool:
        return self._closed

    def add_symbols(self, symbols: Iterable[str]) -> None:
        self._symbols.update(normalize_symbol(symbol) for symbol in symbols)

    def remove_symbols(self, symbols: Iterable[str]) -> None:
        removed = {normalize_symbol(symbol) for symbol in symbols}
        self._symbols.difference_update(removed)
        for symbol in removed:
            self._latest.pop(symbol, None)

    def offer(self, tick: Tick) -> bool:
        """Buffer a tick without blocking. Returns whether it was accepted."""
        if self._closed or tick.symbol not in self._symbols:
            return False
        self._latest[tick.symbol] = tick
        self._event.set()
        return True

    async def wait(self) -> dict[str, Tick]:
        """Wait for buffered ticks and drain the latest value per symbol."""
        await self._event.wait()
        self._event.clear()
        drained = self._latest
        self._latest = {}
        return drained

    def close(self) -> None:
        self._closed = True
        self._event.set()


class EventBus:
    """Fan out ticks to all matching subscriptions without blocking."""

    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    def subscribe(self, symbols: Iterable[str] | None = None) -> Subscription:
        subscription = Subscription(symbols)
        self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        self._subscriptions.discard(subscription)

    def publish(self, tick: Tick) -> int:
        """Offer a tick to subscribers and return the accepted count."""
        accepted = sum(1 for subscription in tuple(self._subscriptions) if subscription.offer(tick))
        return accepted
