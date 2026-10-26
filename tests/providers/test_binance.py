"""Tests for the Binance WebSocket adapter without network access."""

from __future__ import annotations

import json
from typing import Any

from market.models import Tick
from providers.binance import BinanceProvider
from tests.helpers.fakes import FakeClock


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages

    def __aiter__(self) -> _FakeWebSocket:
        return self

    async def __anext__(self) -> str:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


class _FakeConnection:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages

    async def __aenter__(self) -> _FakeWebSocket:
        return _FakeWebSocket(self._messages)

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeConnector:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = [json.dumps(message) for message in messages]
        self.url: str | None = None

    def __call__(self, url: str, **kwargs: Any) -> _FakeConnection:
        self.url = url
        return _FakeConnection(self.messages)


async def test_binance_stream_emits_ticks_and_skips_bad_messages() -> None:
    connector = _FakeConnector(
        [
            {
                "stream": "btcusdt@bookTicker",
                "data": {"s": "BTCUSDT", "b": "100.00", "a": "100.20"},
            },
            {"stream": "btcusdt@bookTicker", "data": {"s": "UNKNOWN", "b": "1", "a": "2"}},
        ]
    )
    provider = BinanceProvider(
        clock=FakeClock(),
        symbols=["BTC/USDT"],
        ws_url="wss://example.test/stream",
        connector=connector,
    )
    ticks: list[Tick] = []

    def sink(tick: Tick) -> None:
        ticks.append(tick)

    await provider._run(sink)

    assert connector.url == "wss://example.test/stream?streams=btcusdt@bookTicker"
    assert len(ticks) == 1
    assert provider.status().last_message_at is not None
