"""GET /rates/{base}/{quote}/candles."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Query

from candles.dependencies import CandleRepositoryDep
from core.exceptions import UnknownSymbolError
from core.security import SettingsDep
from core.symbols import normalize_symbol
from market.models import Candle


async def list_candles(
    base: str,
    quote: str,
    repository: CandleRepositoryDep,
    settings: SettingsDep,
    interval: Annotated[Literal["1m"], Query()] = "1m",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[Candle]:
    try:
        symbol = normalize_symbol(f"{base}/{quote}")
    except ValueError as exc:
        raise UnknownSymbolError(str(exc)) from exc
    if symbol not in settings.symbols:
        raise UnknownSymbolError(f"Unknown symbol {symbol}")
    return await repository.list(symbol=symbol, interval=interval, limit=limit)
