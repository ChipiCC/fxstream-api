"""Tests for shared market models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from market.models import Candle, Rate, Tick
from tests.helpers.fakes import make_tick


def test_tick_normalizes_symbol_and_serializes_decimal() -> None:
    tick = make_tick(symbol="btc/usdt", bid="100.1", ask="100.3")
    assert tick.symbol == "BTC/USDT"
    assert tick.last == Decimal("100.2")


def test_rate_serializes_price_as_string() -> None:
    tick = make_tick()
    rate = Rate(
        symbol=tick.symbol,
        price=tick.last,
        source=tick.source,
        as_of=tick.as_of,
        stale=False,
    )
    payload = rate.model_dump(mode="json")
    assert payload["price"] == "100.1"


def test_tick_rejects_invalid_prices() -> None:
    with pytest.raises(ValidationError):
        make_tick(bid="0", ask="1")
    with pytest.raises(ValidationError):
        make_tick(bid="2", ask="1")


def test_tick_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError):
        Tick(
            symbol="BTC/USDT",
            bid=Decimal("1"),
            ask=Decimal("2"),
            last=Decimal("1.5"),
            source="binance",
            as_of=datetime(2026, 1, 1),
            received_at=datetime(2026, 1, 1),
        )


def test_tick_converts_timestamps_to_utc() -> None:
    tick = make_tick(as_of=datetime(2026, 1, 1, 13, 0, tzinfo=UTC))
    assert tick.as_of.tzinfo is not None
    assert tick.as_of.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_candle_validates_ohlc() -> None:
    Candle(
        symbol="BTC/USDT",
        interval="1m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0.5"),
        close=Decimal("1.5"),
    )
    with pytest.raises(ValidationError):
        Candle(
            symbol="BTC/USDT",
            interval="1m",
            open_time=datetime(2026, 1, 1, tzinfo=UTC),
            open=Decimal("3"),
            high=Decimal("2"),
            low=Decimal("0.5"),
            close=Decimal("1.5"),
        )
    with pytest.raises(ValidationError):
        Candle(
            symbol="BTC/USDT",
            interval="1m",
            open_time=datetime(2026, 1, 1, tzinfo=UTC),
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("2.5"),
            close=Decimal("1.5"),
        )
