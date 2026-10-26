"""Pure provider-payload normalizers.

These functions are deliberately independent of network clients so they can be
unit-tested with recorded payloads.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from core.clock import Clock
from core.symbols import normalize_symbol
from market.models import Tick


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"invalid {field}: {value!r}")
    return parsed


def normalize_binance_book_ticker(
    payload: Mapping[str, Any],
    *,
    pair_map: Mapping[str, str],
    clock: Clock,
) -> Tick:
    """Normalize a Binance ``bookTicker`` payload into a tick."""
    data = payload.get("data", payload)
    if not isinstance(data, Mapping):
        raise ValueError("binance payload data must be an object")

    stream_symbol = str(data.get("s", "")).lower()
    symbol = pair_map.get(stream_symbol)
    if symbol is None:
        raise ValueError(f"unmapped binance symbol {stream_symbol!r}")

    bid = _decimal(data.get("b"), "bid")
    ask = _decimal(data.get("a"), "ask")
    if bid > ask:
        raise ValueError("binance bid cannot be greater than ask")

    received_at = clock.now()
    event_time = data.get("E")
    if isinstance(event_time, int | float):
        as_of = datetime.fromtimestamp(event_time / 1000, tz=UTC)
    else:
        as_of = received_at

    return Tick(
        symbol=normalize_symbol(symbol),
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        source="binance",
        as_of=as_of,
        received_at=received_at,
    )


def normalize_frankfurter_latest(
    payload: Mapping[str, Any],
    *,
    base: str,
    quotes: Iterable[str],
    clock: Clock,
) -> list[Tick]:
    """Normalize a Frankfurter ``/latest`` response into one tick per pair."""
    response_base = str(payload.get("base", "")).upper()
    if response_base != base.upper():
        raise ValueError(f"frankfurter base mismatch: {response_base!r} != {base!r}")

    rates = payload.get("rates")
    if not isinstance(rates, Mapping):
        raise ValueError("frankfurter payload is missing rates")

    try:
        reference_date = date.fromisoformat(str(payload["date"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("frankfurter payload has an invalid date") from exc

    as_of = datetime.combine(reference_date, time.min, tzinfo=UTC)
    received_at = clock.now()
    ticks: list[Tick] = []
    for quote in quotes:
        quote_currency = quote.upper()
        if quote_currency not in rates:
            raise ValueError(f"frankfurter response has no rate for {base}/{quote_currency}")
        price = _decimal(rates[quote_currency], "rate")
        ticks.append(
            Tick(
                symbol=normalize_symbol(f"{base}/{quote_currency}"),
                bid=price,
                ask=price,
                last=price,
                source="frankfurter",
                as_of=as_of,
                received_at=received_at,
            )
        )
    return ticks
