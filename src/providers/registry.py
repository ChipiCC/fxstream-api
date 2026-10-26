"""Provider construction and status registry."""

from __future__ import annotations

from core.clock import Clock
from core.config import Settings
from market.models import ProviderStatus
from providers.base import RateProvider
from providers.binance import BinanceProvider
from providers.frankfurter import FrankfurterProvider


class ProviderRegistry:
    """Own the configured providers and expose their statuses."""

    def __init__(self, providers: list[RateProvider]) -> None:
        self.providers = providers

    def statuses(self) -> list[ProviderStatus]:
        return sorted((provider.status() for provider in self.providers), key=lambda s: s.name)

    def get(self, name: str) -> RateProvider | None:
        return next((provider for provider in self.providers if provider.name == name), None)


def build_providers(settings: Settings, clock: Clock) -> list[RateProvider]:
    """Create the providers enabled by configuration."""
    providers: list[RateProvider] = []
    if settings.binance_symbols:
        providers.append(
            BinanceProvider(
                clock=clock,
                symbols=list(settings.binance_symbols),
                ws_url=settings.binance_ws_url,
                failure_threshold=settings.provider_failure_threshold,
                backoff_initial_seconds=settings.provider_backoff_initial_seconds,
                backoff_max_seconds=settings.provider_backoff_max_seconds,
            )
        )
    if settings.frankfurter_symbols:
        providers.append(
            FrankfurterProvider(
                clock=clock,
                symbols=list(settings.frankfurter_symbols),
                base_url=settings.frankfurter_base_url,
                poll_seconds=settings.frankfurter_poll_seconds,
                timeout_seconds=settings.provider_request_timeout_seconds,
                failure_threshold=settings.provider_failure_threshold,
                backoff_initial_seconds=settings.provider_backoff_initial_seconds,
                backoff_max_seconds=settings.provider_backoff_max_seconds,
            )
        )
    return providers
