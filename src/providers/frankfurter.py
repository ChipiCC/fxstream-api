"""Frankfurter daily FX rates adapter (REST polling)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from core.clock import Clock
from core.symbols import normalize_symbol, split_symbol
from market.models import ProviderState
from providers.base import BaseProvider, Sleep, TickSink
from providers.normalizer import normalize_frankfurter_latest


class FrankfurterProvider(BaseProvider):
    """Poll Frankfurter in batches grouped by base currency."""

    name = "frankfurter"

    def __init__(
        self,
        *,
        clock: Clock,
        symbols: list[str],
        base_url: str,
        poll_seconds: int = 3600,
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep | None = None,
        failure_threshold: int = 3,
        backoff_initial_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            clock=clock,
            failure_threshold=failure_threshold,
            backoff_initial_seconds=backoff_initial_seconds,
            backoff_max_seconds=backoff_max_seconds,
            sleep=sleep,
        )
        self._poll_seconds = poll_seconds
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self._pairs_by_base: dict[str, list[str]] = {}
        for symbol in symbols:
            normalized = normalize_symbol(symbol)
            base, quote = split_symbol(normalized)
            self._pairs_by_base.setdefault(base, []).append(quote)

    async def poll_once(self, sink: TickSink) -> None:
        """Fetch one batch from Frankfurter and emit normalized ticks."""
        for base, quotes in self._pairs_by_base.items():
            response = await self._client.get(
                "/latest",
                params={"from": base, "to": ",".join(quotes)},
            )
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("frankfurter response must be an object")
            ticks = normalize_frankfurter_latest(
                payload,
                base=base,
                quotes=quotes,
                clock=self._clock,
            )
            for tick in ticks:
                self._emit(tick, sink)
        self._set_state(ProviderState.UP)

    async def _run(self, sink: TickSink) -> None:
        while not self.stop_requested():
            await self.poll_once(sink)
            if self.stop_requested():
                break
            await self._sleep(float(self._poll_seconds))

    async def _close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
