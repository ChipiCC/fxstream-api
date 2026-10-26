"""Provider status router."""

from __future__ import annotations

from fastapi import APIRouter

from market.models import ProviderStatus
from providers import handlers

router = APIRouter(prefix="/providers", tags=["providers"])

router.add_api_route(
    "/status",
    handlers.provider_status,
    methods=["GET"],
    response_model=list[ProviderStatus],
    summary="Provider status",
)
