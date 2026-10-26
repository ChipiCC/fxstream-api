"""Repository test doubles.

``InMemoryItemRepository`` implements the same
:class:`~core.repository.BaseRepository` contract as the Postgres
``ItemRepository`` but stores entities in a dict. It lets the CRUD suite run
against a second backend and mirrors the Postgres behaviour that tests rely on:
id/timestamp generation, ``created_at DESC`` ordering, and ``NotFoundError`` on
missing rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from core.exceptions import NotFoundError
from core.repository import BaseRepository
from items.models.item import ItemCreate, ItemRead, ItemUpdate


class InMemoryItemRepository(BaseRepository[ItemRead, ItemCreate, ItemUpdate]):
    """A dict-backed item repository used to test the CRUD contract."""

    def __init__(self) -> None:
        self._items: dict[uuid.UUID, ItemRead] = {}
        self._clock = datetime.min.replace(tzinfo=UTC)

    def _now(self) -> datetime:
        # keep timestamps strictly increasing so created_at ordering is stable
        self._clock = max(datetime.now(UTC), self._clock + timedelta(microseconds=1))
        return self._clock

    async def list(self, *, limit: int, offset: int) -> tuple[list[ItemRead], int]:
        ordered = sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)
        return ordered[offset : offset + limit], len(ordered)

    async def get(self, entity_id: uuid.UUID) -> ItemRead:
        item = self._items.get(entity_id)
        if item is None:
            raise NotFoundError(f"Item {entity_id} not found")
        return item

    async def create(self, payload: ItemCreate) -> ItemRead:
        now = self._now()
        item = ItemRead(
            id=uuid.uuid4(),
            name=payload.name,
            description=payload.description,
            created_at=now,
            updated_at=now,
        )
        self._items[item.id] = item
        return item

    async def update(self, entity_id: uuid.UUID, payload: ItemUpdate) -> ItemRead:
        item = self._items.get(entity_id)
        if item is None:
            raise NotFoundError(f"Item {entity_id} not found")
        updated = item.model_copy(
            update={**payload.model_dump(exclude_unset=True), "updated_at": self._now()}
        )
        self._items[entity_id] = updated
        return updated

    async def delete(self, entity_id: uuid.UUID) -> None:
        if self._items.pop(entity_id, None) is None:
            raise NotFoundError(f"Item {entity_id} not found")
