"""Quote dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from market.dependencies import MarketDep
from quotes.engine import QuoteEngine


def get_quote_engine(market: MarketDep) -> QuoteEngine:
    return market.quote_engine


QuoteEngineDep = Annotated[QuoteEngine, Depends(get_quote_engine)]
