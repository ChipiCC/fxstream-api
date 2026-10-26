"""POST /items — create an item."""

from __future__ import annotations

from items.dependencies import ItemServiceDep
from items.models import ItemCreate, ItemRead


async def create_item(payload: ItemCreate, service: ItemServiceDep) -> ItemRead:
    return await service.create(payload)
