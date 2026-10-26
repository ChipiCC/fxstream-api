"""WebSocket rate stream route."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from market.runtime import MarketRuntime
from streaming.session import RateStreamSession

router = APIRouter(tags=["streaming"])


@router.websocket("/ws/rates")
async def rates_stream(websocket: WebSocket) -> None:
    market: MarketRuntime = websocket.app.state.market
    await RateStreamSession(websocket, market).run()
