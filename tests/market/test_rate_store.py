"""Tests for the latest-rate cache and staleness calculation."""

from __future__ import annotations

from decimal import Decimal

from market.rate_store import RateStore
from tests.helpers.fakes import FakeClock, make_tick


def test_update_get_and_snapshot() -> None:
    clock = FakeClock()
    store = RateStore(clock=clock, stale_seconds={"binance": 10})
    btc = make_tick(symbol="BTC/USDT", clock=clock)
    eur = make_tick(symbol="EUR/USD", source="frankfurter", clock=clock)

    store.update(btc)
    store.update(eur)

    assert store.latest_tick("btc/usdt") == btc
    assert store.get("BTC/USDT") is not None
    assert [rate.symbol for rate in store.snapshot()] == ["BTC/USDT", "EUR/USD"]
    assert [rate.symbol for rate in store.snapshot(["EUR/USD"])] == ["EUR/USD"]
    assert store.snapshot(["GBP/USD"]) == []


def test_price_is_midpoint() -> None:
    clock = FakeClock()
    store = RateStore(clock=clock, stale_seconds={"binance": 10})
    store.update(make_tick(bid="100", ask="102", clock=clock))
    rate = store.get("BTC/USDT")
    assert rate is not None
    assert rate.price == Decimal("101")


def test_staleness_uses_as_of_and_threshold() -> None:
    clock = FakeClock()
    store = RateStore(clock=clock, stale_seconds={"binance": 10, "frankfurter": 1000})
    store.update(make_tick(source="binance", clock=clock))
    store.update(make_tick(symbol="EUR/USD", source="frankfurter", clock=clock))

    clock.advance(11)
    assert store.get("BTC/USDT").stale is True  # type: ignore[union-attr]
    assert store.get("EUR/USD").stale is False  # type: ignore[union-attr]


def test_unknown_provider_is_stale() -> None:
    clock = FakeClock()
    store = RateStore(clock=clock, stale_seconds={})
    store.update(make_tick(source="unknown", clock=clock))
    assert store.get("BTC/USDT").stale is True  # type: ignore[union-attr]


def test_missing_symbol_returns_none() -> None:
    store = RateStore(clock=FakeClock(), stale_seconds={})
    assert store.get("BTC/USDT") is None
    assert store.latest_tick("BTC/USDT") is None
