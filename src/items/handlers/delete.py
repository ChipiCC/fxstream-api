"""DELETE /items/{item_id} — delete an item."""

from __future__ import annotations

import uuid

from items.dependencies import ItemServiceDep


async def delete_item(item_id: uuid.UUID, service: ItemServiceDep) -> None:
    await service.delete(item_id)
