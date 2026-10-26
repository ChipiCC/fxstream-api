"""Rate dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from market.dependencies import MarketDep
from market.rate_store import RateStore


def get_rate_store(market: MarketDep) -> RateStore:
    return market.rate_store


RateStoreDep = Annotated[RateStore, Depends(get_rate_store)]
