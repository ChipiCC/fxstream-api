"""PATCH /items/{item_id} — update an item."""

from __future__ import annotations

import uuid

from items.dependencies import ItemServiceDep
from items.models import ItemRead, ItemUpdate


async def update_item(item_id: uuid.UUID, payload: ItemUpdate, service: ItemServiceDep) -> ItemRead:
    return await service.update(item_id, payload)
