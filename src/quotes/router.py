"""Quote router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from core.security import require_api_key
from quotes import handlers
from quotes.models import Quote, QuoteStatus

router = APIRouter(
    prefix="/quotes",
    tags=["quotes"],
    dependencies=[Depends(require_api_key)],
)

router.add_api_route(
    "",
    handlers.create_quote,
    methods=["POST"],
    response_model=Quote,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quote",
)
router.add_api_route(
    "/{quote_id}",
    handlers.get_quote,
    methods=["GET"],
    response_model=QuoteStatus,
    summary="Get a quote",
)
