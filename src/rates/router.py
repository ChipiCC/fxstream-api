"""Rate snapshot router."""

from __future__ import annotations

from fastapi import APIRouter

from market.models import Rate
from rates import handlers

router = APIRouter(tags=["rates"])

router.add_api_route(
    "/rates",
    handlers.list_rates,
    methods=["GET"],
    response_model=list[Rate],
    summary="Latest rate snapshot",
)
