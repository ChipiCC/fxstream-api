"""Tests for provider construction and status aggregation."""

from __future__ import annotations

from core.config import Settings
from providers.registry import ProviderRegistry, build_providers
from tests.helpers.fakes import FakeClock, FakeProvider


async def test_build_providers_from_settings() -> None:
    settings = Settings(
        binance_symbols="BTC/USDT",
        frankfurter_symbols="EUR/USD",
    )
    providers = build_providers(settings, FakeClock())
    try:
        assert [provider.name for provider in providers] == ["binance", "frankfurter"]
        registry = ProviderRegistry(providers)
        assert [status.name for status in registry.statuses()] == ["binance", "frankfurter"]
        assert registry.get("binance") is providers[0]
        assert registry.get("missing") is None
    finally:
        for provider in providers:
            await provider.stop()


async def test_empty_symbols_disable_providers() -> None:
    settings = Settings(binance_symbols="", frankfurter_symbols="")
    providers = build_providers(settings, FakeClock())
    assert providers == []


def test_registry_statuses_are_sorted() -> None:
    registry = ProviderRegistry([FakeProvider()])
    assert registry.statuses()[0].name == "fake"
