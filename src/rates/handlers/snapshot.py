"""GET /rates."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from core.exceptions import UnknownSymbolError
from core.security import SettingsDep
from core.symbols import normalize_symbol
from market.models import Rate
from rates.dependencies import RateStoreDep


async def list_rates(
    rate_store: RateStoreDep,
    settings: SettingsDep,
    symbols: Annotated[
        str | None,
        Query(description="Comma-separated BASE/QUOTE symbols; defaults to all configured"),
    ] = None,
) -> list[Rate]:
    configured = set(settings.symbols)
    if symbols is None:
        requested = settings.symbols
    else:
        requested = []
        for raw in symbols.split(","):
            value = raw.strip()
            if not value:
                continue
            try:
                symbol = normalize_symbol(value)
            except ValueError as exc:
                raise UnknownSymbolError(str(exc)) from exc
            if symbol not in configured:
                raise UnknownSymbolError(f"Unknown symbol {symbol}")
            requested.append(symbol)
    return rate_store.snapshot(requested)
