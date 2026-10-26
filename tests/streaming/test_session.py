"""Tests for the WebSocket subscription protocol and backpressure."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from market.runtime import MarketRuntime
from streaming.session import RateStreamSession
from tests.helpers.fakes import make_tick


class _FakeWebSocket:
    def __init__(self, incoming: list[str] | None = None) -> None:
        self.incoming = incoming or []
        self.sent: list[dict[str, Any]] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if self.incoming:
            return self.incoming.pop(0)
        raise WebSocketDisconnect()

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)


def _session(market: MarketRuntime) -> tuple[RateStreamSession, _FakeWebSocket]:
    websocket = _FakeWebSocket()
    return RateStreamSession(cast(WebSocket, websocket), market), websocket


async def test_subscribe_sends_latest_snapshot_and_unsubscribes(
    market: MarketRuntime,
) -> None:
    market.rate_store.update(make_tick(clock=market.clock))
    session, _websocket = _session(market)
    subscription = market.event_bus.subscribe()
    try:
        await session._handle_message(
            {"action": "subscribe", "symbols": ["BTC/USDT"]},
            subscription,
        )
        assert subscription.symbols == frozenset({"BTC/USDT"})
        ticks = await subscription.wait()
        assert ticks["BTC/USDT"].symbol == "BTC/USDT"

        sender = asyncio.create_task(session._send_loop(subscription))
        await asyncio.sleep(0)
        subscription.close()
        await asyncio.gather(sender, return_exceptions=True)

        await session._handle_message(
            {"action": "unsubscribe", "symbols": ["BTC/USDT"]},
            subscription,
        )
        assert subscription.symbols == frozenset()
    finally:
        subscription.close()
        market.event_bus.unsubscribe(subscription)


async def test_run_reports_invalid_json_and_disconnects(market: MarketRuntime) -> None:
    websocket = _FakeWebSocket(["not-json"])
    session = RateStreamSession(cast(WebSocket, websocket), market)

    await session.run()

    assert websocket.accepted is True
    assert websocket.sent[0]["type"] == "error"
    assert websocket.sent[0]["code"] == "invalid_json"


async def test_handle_message_errors(market: MarketRuntime) -> None:
    session, websocket = _session(market)
    subscription = market.event_bus.subscribe()
    try:
        await session._handle_message("not-an-object", subscription)
        await session._handle_message({"action": "hold"}, subscription)
        await session._handle_message({"action": "subscribe", "symbols": []}, subscription)
        await session._handle_message({"action": "subscribe", "symbols": ["bad"]}, subscription)
        await session._handle_message(
            {"action": "subscribe", "symbols": ["DOGE/USD"]}, subscription
        )
    finally:
        subscription.close()

    assert [message["code"] for message in websocket.sent] == [
        "invalid_message",
        "invalid_action",
        "invalid_symbols",
        "invalid_symbol",
        "unknown_symbol",
    ]


async def test_send_loop_coalesces_latest_tick(market: MarketRuntime) -> None:
    session, websocket = _session(market)
    subscription = market.event_bus.subscribe(["BTC/USDT"])
    subscription.offer(make_tick(bid="100", ask="102", clock=market.clock))
    subscription.offer(make_tick(bid="200", ask="202", clock=market.clock))
    sender = asyncio.create_task(session._send_loop(subscription))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    subscription.close()
    await asyncio.gather(sender, return_exceptions=True)

    tick_messages = [message for message in websocket.sent if message["type"] == "tick"]
    assert len(tick_messages) == 1
    assert tick_messages[0]["bid"] == "200"

    market.event_bus.unsubscribe(subscription)


async def test_subscribe_message_round_trip(market: MarketRuntime) -> None:
    websocket = _FakeWebSocket([json.dumps({"action": "subscribe", "symbols": ["BTC/USDT"]})])
    session = RateStreamSession(cast(WebSocket, websocket), market)
    await session.run()
    assert websocket.accepted is True
