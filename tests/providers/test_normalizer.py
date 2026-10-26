"""Fixture-driven tests for provider payload normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from providers.normalizer import (
    normalize_binance_book_ticker,
    normalize_frankfurter_latest,
)
from tests.helpers.fakes import FakeClock


def test_normalize_binance_combined_stream() -> None:
    clock = FakeClock()
    tick = normalize_binance_book_ticker(
        {
            "stream": "btcusdt@bookTicker",
            "data": {"s": "BTCUSDT", "b": "100.00", "a": "100.20", "E": 1767272400000},
        },
        pair_map={"btcusdt": "BTC/USDT"},
        clock=clock,
    )
    assert tick.symbol == "BTC/USDT"
    assert tick.bid == Decimal("100.00")
    assert tick.ask == Decimal("100.20")
    assert tick.last == Decimal("100.10")
    assert tick.source == "binance"
    assert tick.as_of == datetime.fromtimestamp(1767272400, tz=UTC)
    assert tick.received_at == clock.now()


def test_normalize_binance_plain_payload_uses_receive_time() -> None:
    clock = FakeClock()
    tick = normalize_binance_book_ticker(
        {"s": "BTCUSDT", "b": "100", "a": "101"},
        pair_map={"btcusdt": "BTC/USDT"},
        clock=clock,
    )
    assert tick.as_of == clock.now()


@pytest.mark.parametrize(
    ("payload", "pair_map"),
    [
        ({"data": {"s": "ETHUSDT", "b": "1", "a": "2"}}, {"btcusdt": "BTC/USDT"}),
        ({"data": {"s": "BTCUSDT", "b": "0", "a": "2"}}, {"btcusdt": "BTC/USDT"}),
        ({"data": {"s": "BTCUSDT", "b": "3", "a": "2"}}, {"btcusdt": "BTC/USDT"}),
        ({"data": "not-an-object"}, {"btcusdt": "BTC/USDT"}),
        ({"data": {"s": "BTCUSDT", "b": "abc", "a": "2"}}, {"btcusdt": "BTC/USDT"}),
    ],
)
def test_normalize_binance_rejects_invalid_payloads(
    payload: dict[str, object], pair_map: dict[str, str]
) -> None:
    with pytest.raises(ValueError):
        normalize_binance_book_ticker(payload, pair_map=pair_map, clock=FakeClock())


def test_normalize_frankfurter_latest() -> None:
    clock = FakeClock()
    ticks = normalize_frankfurter_latest(
        {
            "amount": 1.0,
            "base": "EUR",
            "date": "2026-10-26",
            "rates": {"USD": 1.08, "GBP": 0.86},
        },
        base="EUR",
        quotes=["USD", "GBP"],
        clock=clock,
    )
    assert [tick.symbol for tick in ticks] == ["EUR/USD", "EUR/GBP"]
    assert ticks[0].bid == ticks[0].ask == ticks[0].last == Decimal("1.08")
    assert ticks[0].as_of == datetime(2026, 10, 26, tzinfo=UTC)
    assert ticks[0].source == "frankfurter"


def test_normalize_frankfurter_rejects_base_mismatch() -> None:
    with pytest.raises(ValueError):
        normalize_frankfurter_latest(
            {"base": "USD", "date": "2026-10-26", "rates": {"EUR": 1}},
            base="EUR",
            quotes=["EUR"],
            clock=FakeClock(),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"base": "EUR", "date": "2026-10-26"},
        {"base": "EUR", "date": "not-a-date", "rates": {"USD": 1}},
        {"base": "EUR", "date": "2026-10-26", "rates": {"GBP": 1}},
        {"base": "EUR", "date": "2026-10-26", "rates": {"USD": "abc"}},
    ],
)
def test_normalize_frankfurter_rejects_invalid_payloads(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        normalize_frankfurter_latest(
            payload,
            base="EUR",
            quotes=["USD"],
            clock=FakeClock(),
        )
