"""GET /health/live — liveness probe."""

from __future__ import annotations

from internal.models import Liveness


async def liveness() -> Liveness:
    """Return OK if the process is up. Does not touch dependencies."""
    return Liveness(status="ok")
