"""GET /quotes/{quote_id}."""

from __future__ import annotations

import uuid

from quotes.dependencies import QuoteEngineDep
from quotes.models import QuoteStatus


async def get_quote(quote_id: uuid.UUID, engine: QuoteEngineDep) -> QuoteStatus:
    return engine.get(quote_id)
