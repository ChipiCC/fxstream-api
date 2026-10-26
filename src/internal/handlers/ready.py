"""GET /health/ready — readiness probe."""

from __future__ import annotations

from fastapi import Response, status
from sqlalchemy import text

from core.config import get_settings
from db.session import SessionDep
from internal.models import Readiness

settings = get_settings()


async def readiness(response: Response, session: SessionDep) -> Readiness:
    """Return OK only if dependencies (database) are reachable.

    Responds 503 when a dependency is down so orchestrators stop routing traffic
    to the instance.
    """
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Readiness(status="error", environment=settings.environment, checks=checks)

    return Readiness(status="ok", environment=settings.environment, checks=checks)
