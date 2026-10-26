"""In-memory quote store with expiry retention."""

from __future__ import annotations

import uuid
from datetime import timedelta

from core.clock import Clock
from quotes.models import Quote


class QuoteStore:
    """Keep quotes in process memory, evicting them after the grace period."""

    def __init__(self, *, clock: Clock, retention_seconds: int) -> None:
        self._clock = clock
        self._retention = timedelta(seconds=retention_seconds)
        self._quotes: dict[uuid.UUID, Quote] = {}

    def put(self, quote: Quote) -> None:
        self._quotes[quote.quote_id] = quote
        self.prune()

    def get(self, quote_id: uuid.UUID) -> Quote | None:
        self.prune()
        return self._quotes.get(quote_id)

    def prune(self) -> None:
        cutoff = self._clock.now() - self._retention
        expired = [
            quote_id for quote_id, quote in self._quotes.items() if quote.expires_at < cutoff
        ]
        for quote_id in expired:
            del self._quotes[quote_id]

    def __len__(self) -> int:
        return len(self._quotes)
