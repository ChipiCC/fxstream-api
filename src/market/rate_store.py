"""In-memory latest-tick cache with per-provider staleness."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from core.clock import Clock
from core.symbols import normalize_symbol
from market.models import Rate, Tick


class RateStore:
    """Keep the latest normalized tick for each symbol.

    The store is intentionally process-local: rates are not shared across
    workers. See AGENTS.md and ``docs/architecture.md``.
    """

    def __init__(self, *, clock: Clock, stale_seconds: Mapping[str, int]) -> None:
        self._clock = clock
        self._stale_seconds = dict(stale_seconds)
        self._ticks: dict[str, Tick] = {}

    def update(self, tick: Tick) -> None:
        """Store a tick, replacing the previous value for the symbol."""
        self._ticks[tick.symbol] = tick

    def latest_tick(self, symbol: str) -> Tick | None:
        return self._ticks.get(normalize_symbol(symbol))

    def get(self, symbol: str) -> Rate | None:
        tick = self.latest_tick(symbol)
        return self._to_rate(tick) if tick is not None else None

    def snapshot(self, symbols: Iterable[str] | None = None) -> list[Rate]:
        """Return current rates, optionally restricted to ``symbols``."""
        selected: Iterable[str]
        if symbols is None:
            selected = self._ticks.keys()
        else:
            selected = [normalize_symbol(symbol) for symbol in symbols]
        rates = [self._to_rate(self._ticks[symbol]) for symbol in selected if symbol in self._ticks]
        return sorted(rates, key=lambda rate: rate.symbol)

    def is_stale(self, tick: Tick) -> bool:
        threshold = self._stale_seconds.get(tick.source)
        if threshold is None:
            return True
        age_seconds = (self._clock.now() - tick.as_of).total_seconds()
        return age_seconds > threshold

    def _to_rate(self, tick: Tick) -> Rate:
        return Rate(
            symbol=tick.symbol,
            price=(tick.bid + tick.ask) / 2,
            source=tick.source,
            as_of=tick.as_of,
            stale=self.is_stale(tick),
        )
