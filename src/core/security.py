"""API-key authentication.

Authentication is opt-in: when ``API_KEYS`` is empty the guard is a no-op
(intended for local development). Configure one or more keys to require the
``X-API-Key`` header on protected routes. See ``docs/authentication.md``.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

from core.config import Settings, get_settings
from core.exceptions import UnauthorizedError

SettingsDep = Annotated[Settings, Depends(get_settings)]

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    settings: SettingsDep,
) -> None:
    """Require a valid API key when any are configured."""
    if not settings.api_keys:
        return
    if api_key is not None and any(
        secrets.compare_digest(api_key, key) for key in settings.api_keys
    ):
        return
    raise UnauthorizedError("Invalid or missing API key")
