"""Items domain router — a thin HTTP layer over :class:`ItemService`.

Paths map to the per-endpoint handlers in ``items/handlers/``; the router only
wires routes and response metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from core.pagination import Page
from core.security import require_api_key
from items import handlers
from items.models import ItemRead

router = APIRouter(
    prefix="/items",
    tags=["items"],
    dependencies=[Depends(require_api_key)],
)

router.add_api_route(
    "",
    handlers.list_items,
    methods=["GET"],
    response_model=Page[ItemRead],
    summary="List items",
)
router.add_api_route(
    "",
    handlers.create_item,
    methods=["POST"],
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
)
router.add_api_route(
    "/{item_id}",
    handlers.get_item,
    methods=["GET"],
    response_model=ItemRead,
    summary="Get an item",
)
router.add_api_route(
    "/{item_id}",
    handlers.update_item,
    methods=["PATCH"],
    response_model=ItemRead,
    summary="Update an item",
)
router.add_api_route(
    "/{item_id}",
    handlers.delete_item,
    methods=["DELETE"],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
)
