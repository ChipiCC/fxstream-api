"""WebSocket subscription protocol with latest-per-symbol backpressure."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from core.logging import get_logger
from core.metrics import WS_MESSAGES, WS_SUBSCRIBERS
from core.symbols import normalize_symbol
from market.event_bus import Subscription
from market.models import Tick
from market.runtime import MarketRuntime

logger = get_logger(__name__)


class RateStreamSession:
    """Serve one WebSocket client for its lifetime."""

    def __init__(self, websocket: WebSocket, market: MarketRuntime) -> None:
        self._websocket = websocket
        self._market = market
        self._send_lock = asyncio.Lock()

    async def run(self) -> None:
        await self._websocket.accept()
        subscription = self._market.event_bus.subscribe()
        WS_SUBSCRIBERS.inc()
        sender = asyncio.create_task(self._send_loop(subscription), name="ws-rate-sender")
        try:
            while True:
                raw = await self._websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_error("invalid_json", "Message must be valid JSON")
                    continue
                await self._handle_message(message, subscription)
        except WebSocketDisconnect:
            pass
        finally:
            subscription.close()
            self._market.event_bus.unsubscribe(subscription)
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
            WS_SUBSCRIBERS.dec()

    async def _handle_message(self, message: Any, subscription: Subscription) -> None:
        if not isinstance(message, dict):
            await self._send_error("invalid_message", "Expected a JSON object")
            return

        action = message.get("action")
        if action not in {"subscribe", "unsubscribe"}:
            await self._send_error("invalid_action", "Action must be subscribe or unsubscribe")
            return

        raw_symbols = message.get("symbols")
        if not isinstance(raw_symbols, list) or not raw_symbols:
            await self._send_error("invalid_symbols", "symbols must be a non-empty array")
            return

        try:
            symbols = [normalize_symbol(str(symbol)) for symbol in raw_symbols]
        except ValueError as exc:
            await self._send_error("invalid_symbol", str(exc))
            return

        configured = set(self._market.settings.symbols)
        unknown = sorted(set(symbols) - configured)
        if unknown:
            await self._send_error(
                "unknown_symbol",
                f"Unknown symbols: {', '.join(unknown)}",
            )
            return

        if action == "subscribe":
            new_symbols = set(symbols) - set(subscription.symbols)
            subscription.add_symbols(symbols)
            for symbol in new_symbols:
                tick = self._market.rate_store.latest_tick(symbol)
                if tick is not None:
                    subscription.offer(tick)
        else:
            subscription.remove_symbols(symbols)

    async def _send_loop(self, subscription: Subscription) -> None:
        try:
            while not subscription.closed:
                ticks = await subscription.wait()
                for tick in sorted(ticks.values(), key=lambda item: item.symbol):
                    await self._send_tick(tick)
        except WebSocketDisconnect, RuntimeError:
            return

    async def _send_tick(self, tick: Tick) -> None:
        rate = self._market.rate_store.get(tick.symbol)
        payload = {
            "type": "tick",
            "symbol": tick.symbol,
            "bid": _decimal_string(tick.bid),
            "ask": _decimal_string(tick.ask),
            "source": tick.source,
            "as_of": tick.as_of.isoformat(),
            "stale": rate.stale if rate is not None else False,
        }
        await self._send(payload)
        WS_MESSAGES.labels(outcome="tick").inc()

    async def _send_error(self, code: str, message: str) -> None:
        await self._send({"type": "error", "code": code, "message": message})
        WS_MESSAGES.labels(outcome="error").inc()

    async def _send(self, payload: dict[str, Any]) -> None:
        async with self._send_lock:
            await self._websocket.send_json(payload)


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")
