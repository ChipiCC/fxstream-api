"""Build and expose the process-local market data runtime."""

from __future__ import annotations

from dataclasses import dataclass

from candles.aggregator import CandleAggregator
from candles.writer import CandleWriter
from core.clock import Clock, SystemClock
from core.config import Settings, get_settings
from ingestion.manager import IngestionManager
from market.event_bus import EventBus
from market.rate_store import RateStore
from providers.base import RateProvider
from providers.registry import ProviderRegistry, build_providers
from quotes.engine import QuoteEngine
from quotes.store import QuoteStore


@dataclass(slots=True)
class MarketRuntime:
    """The in-memory services that make up a single FXStream process."""

    settings: Settings
    clock: Clock
    rate_store: RateStore
    event_bus: EventBus
    quote_store: QuoteStore
    quote_engine: QuoteEngine
    registry: ProviderRegistry
    aggregator: CandleAggregator | None
    manager: IngestionManager


def build_market_runtime(
    *,
    settings: Settings | None = None,
    clock: Clock | None = None,
    providers: list[RateProvider] | None = None,
) -> MarketRuntime:
    """Construct a fresh runtime, optionally with injected providers/clock."""
    resolved_settings = settings or get_settings()
    resolved_clock = clock or SystemClock()
    rate_store = RateStore(
        clock=resolved_clock,
        stale_seconds=resolved_settings.provider_stale_seconds,
    )
    event_bus = EventBus()
    quote_store = QuoteStore(
        clock=resolved_clock,
        retention_seconds=resolved_settings.quote_retention_seconds,
    )
    quote_engine = QuoteEngine(
        rate_store=rate_store,
        store=quote_store,
        clock=resolved_clock,
        spreads=resolved_settings.spreads_bps,
        default_spread_bps=resolved_settings.default_spread_bps,
        price_decimals=resolved_settings.price_decimals,
        price_decimals_by_symbol=resolved_settings.price_decimals_by_symbol,
        ttl_seconds=resolved_settings.quote_ttl_seconds,
    )
    resolved_providers = (
        build_providers(resolved_settings, resolved_clock) if providers is None else providers
    )
    registry = ProviderRegistry(resolved_providers)
    aggregator = (
        CandleAggregator(
            writer=CandleWriter(),
            clock=resolved_clock,
            flush_seconds=resolved_settings.candle_flush_seconds,
        )
        if resolved_settings.candles_enabled
        else None
    )
    manager = IngestionManager(
        rate_store=rate_store,
        event_bus=event_bus,
        providers=resolved_providers,
        aggregator=aggregator,
    )
    return MarketRuntime(
        settings=resolved_settings,
        clock=resolved_clock,
        rate_store=rate_store,
        event_bus=event_bus,
        quote_store=quote_store,
        quote_engine=quote_engine,
        registry=registry,
        aggregator=aggregator,
        manager=manager,
    )
