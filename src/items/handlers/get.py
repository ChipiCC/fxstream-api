"""GET /items/{item_id} — read an item."""

from __future__ import annotations

import uuid

from items.dependencies import ItemServiceDep
from items.models import ItemRead


async def get_item(item_id: uuid.UUID, service: ItemServiceDep) -> ItemRead:
    return await service.get(item_id)
