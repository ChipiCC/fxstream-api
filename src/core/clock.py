"""Injectable clocks for deterministic expiry and staleness tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Minimal clock contract used by market and quote domain code."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""
        ...


class SystemClock:
    """Production clock backed by the system clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)
