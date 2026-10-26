"""GET / — service metadata."""

from __future__ import annotations

from core.config import get_settings
from core.version import __version__
from internal.models import ServiceInfo

settings = get_settings()


async def service_info() -> ServiceInfo:
    return ServiceInfo(service=settings.app_name, version=__version__, docs="/docs")
