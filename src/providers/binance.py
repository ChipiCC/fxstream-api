"""Binance ``bookTicker`` WebSocket adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from websockets.asyncio.client import connect as ws_connect

from core.clock import Clock
from core.symbols import normalize_symbol
from market.models import ProviderState
from providers.base import BaseProvider, TickSink
from providers.normalizer import normalize_binance_book_ticker

Connector = Callable[..., Any]


class BinanceProvider(BaseProvider):
    """Stream best bid/ask prices for configured crypto pairs."""

    name = "binance"

    def __init__(
        self,
        *,
        clock: Clock,
        symbols: list[str],
        ws_url: str,
        connector: Connector = ws_connect,
        failure_threshold: int = 3,
        backoff_initial_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            clock=clock,
            failure_threshold=failure_threshold,
            backoff_initial_seconds=backoff_initial_seconds,
            backoff_max_seconds=backoff_max_seconds,
        )
        self._connector = connector
        self._symbols = [normalize_symbol(symbol) for symbol in symbols]
        self._pair_map = {symbol.replace("/", "").lower(): symbol for symbol in self._symbols}
        streams = "/".join(f"{pair}@bookTicker" for pair in self._pair_map)
        separator = "&" if "?" in ws_url else "?"
        self._url = f"{ws_url.rstrip('/')}{separator}streams={streams}" if streams else ws_url

    async def _run(self, sink: TickSink) -> None:
        async with self._connector(
            self._url,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=10,
        ) as websocket:
            self._set_state(ProviderState.UP)
            async for raw in websocket:
                if self.stop_requested():
                    break
                try:
                    payload = json.loads(raw)
                    tick = normalize_binance_book_ticker(
                        payload,
                        pair_map=self._pair_map,
                        clock=self._clock,
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    self._record_message_error(exc)
                    continue
                self._emit(tick, sink)
