"""Business logic for items.

The service is a thin layer over :class:`ItemRepository`; persistence and SQL
live in the repository (see ``items/repository.py``).
"""

from __future__ import annotations

import uuid

from items.models.item import ItemCreate, ItemRead, ItemUpdate
from items.repository import ItemRepository


class ItemService:
    """Business logic for the ``items`` domain."""

    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    async def list(self, *, limit: int, offset: int) -> tuple[list[ItemRead], int]:
        """Return a page of items and the total row count."""
        return await self.repository.list(limit=limit, offset=offset)

    async def get(self, item_id: uuid.UUID) -> ItemRead:
        return await self.repository.get(item_id)

    async def create(self, payload: ItemCreate) -> ItemRead:
        return await self.repository.create(payload)

    async def update(self, item_id: uuid.UUID, payload: ItemUpdate) -> ItemRead:
        return await self.repository.update(item_id, payload)

    async def delete(self, item_id: uuid.UUID) -> None:
        await self.repository.delete(item_id)
