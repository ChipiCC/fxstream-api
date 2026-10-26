"""Candle history router."""

from __future__ import annotations

from fastapi import APIRouter

from candles import handlers
from market.models import Candle

router = APIRouter(tags=["candles"])

router.add_api_route(
    "/rates/{base}/{quote}/candles",
    handlers.list_candles,
    methods=["GET"],
    response_model=list[Candle],
    summary="Historical candles",
)
