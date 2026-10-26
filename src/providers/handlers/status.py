"""GET /providers/status."""

from __future__ import annotations

from market.dependencies import MarketDep
from market.models import ProviderStatus


async def provider_status(market: MarketDep) -> list[ProviderStatus]:
    return market.registry.statuses()
