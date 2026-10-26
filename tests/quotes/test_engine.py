"""Tests for quote generation, spread math, and expiry."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from core.exceptions import NotFoundError, RateUnavailableError, StaleRateError
from market.models import Side
from market.rate_store import RateStore
from quotes.engine import QuoteEngine
from quotes.models import QuoteCreate
from quotes.store import QuoteStore
from tests.helpers.fakes import FakeClock, make_tick


def build_engine(
    *,
    clock: FakeClock | None = None,
    ttl_seconds: int = 30,
    retention_seconds: int = 300,
) -> tuple[QuoteEngine, QuoteStore, RateStore, FakeClock]:
    fake_clock = clock or FakeClock()
    rate_store = RateStore(
        clock=fake_clock,
        stale_seconds={"binance": 10, "frankfurter": 1000},
    )
    store = QuoteStore(clock=fake_clock, retention_seconds=retention_seconds)
    engine = QuoteEngine(
        rate_store=rate_store,
        store=store,
        clock=fake_clock,
        spreads={"BTC/USDT": 10},
        default_spread_bps=5,
        price_decimals=2,
        price_decimals_by_symbol={"EUR/USD": 4},
        ttl_seconds=ttl_seconds,
    )
    return engine, store, rate_store, fake_clock


def test_quote_uses_half_spread_and_decimal_precision() -> None:
    engine, store, rate_store, _clock = build_engine()
    rate_store.update(make_tick(bid="100", ask="100.2"))

    quote = engine.create(QuoteCreate(symbol="BTC/USDT", side=Side.BUY, amount=Decimal("1")))

    assert quote.mid == Decimal("100.10")
    assert quote.bid == Decimal("100.05")
    assert quote.ask == Decimal("100.15")
    assert quote.price == Decimal("100.15")
    assert quote.side is Side.BUY
    assert quote.amount == Decimal("1")
    assert store.get(quote.quote_id) == quote


def test_sell_quote_uses_bid_price() -> None:
    engine, _store, rate_store, _clock = build_engine()
    rate_store.update(make_tick(bid="100", ask="100.2"))

    quote = engine.create(QuoteCreate(symbol="BTC/USDT", side=Side.SELL))
    assert quote.price == quote.bid


def test_quote_rejects_missing_rate() -> None:
    engine, _store, _rate_store, _clock = build_engine()
    with pytest.raises(RateUnavailableError):
        engine.create(QuoteCreate(symbol="BTC/USDT", side=Side.BUY))


def test_quote_rejects_stale_rate() -> None:
    engine, _store, rate_store, clock = build_engine()
    rate_store.update(make_tick())
    clock.advance(11)

    with pytest.raises(StaleRateError):
        engine.create(QuoteCreate(symbol="BTC/USDT", side=Side.BUY))


def test_quote_becomes_invalid_then_is_evicted() -> None:
    engine, _store, rate_store, clock = build_engine(ttl_seconds=30, retention_seconds=60)
    rate_store.update(make_tick())
    quote = engine.create(QuoteCreate(symbol="BTC/USDT", side=Side.BUY))

    assert engine.get(quote.quote_id).valid is True
    clock.advance(31)
    assert engine.get(quote.quote_id).valid is False

    clock.advance(121)
    with pytest.raises(NotFoundError):
        engine.get(quote.quote_id)


def test_get_missing_quote_raises_not_found() -> None:
    engine, _store, _rate_store, _clock = build_engine()
    with pytest.raises(NotFoundError):
        engine.get(uuid.uuid4())


def test_per_symbol_precision_override() -> None:
    engine, _store, rate_store, _clock = build_engine()
    rate_store.update(
        make_tick(
            symbol="EUR/USD",
            bid="1.0800",
            ask="1.0802",
            source="frankfurter",
            last="1.0801",
        )
    )
    quote = engine.create(QuoteCreate(symbol="EUR/USD", side=Side.BUY))
    assert quote.bid.as_tuple().exponent == -4
