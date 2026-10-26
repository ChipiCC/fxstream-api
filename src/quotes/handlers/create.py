"""POST /quotes."""

from __future__ import annotations

from quotes.dependencies import QuoteEngineDep
from quotes.models import Quote, QuoteCreate


async def create_quote(payload: QuoteCreate, engine: QuoteEngineDep) -> Quote:
    return engine.create(payload)
