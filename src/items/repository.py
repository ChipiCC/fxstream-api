"""Postgres repository for items.

Native, parameterized SQL — no ORM. See AGENTS.md for the SQL conventions.
Repositories do not manage transactions: the session dependency commits once per
request (see ``docs/database.md``).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from core.repository import BaseRepository
from items.models.item import ItemCreate, ItemRead, ItemUpdate

# Columns returned to the API
_COLUMNS = "id, name, description, created_at, updated_at"

# Fields a client may change; whitelists the dynamic UPDATE
_MUTABLE_FIELDS = frozenset({"name", "description"})

_LIST_ITEMS = text(
    "SELECT id, name, description, created_at, updated_at FROM items "
    "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
)
_COUNT_ITEMS = text("SELECT count(*) FROM items")
_GET_ITEM = text("SELECT id, name, description, created_at, updated_at FROM items WHERE id = :id")
# clock_timestamp() (not CURRENT_TIMESTAMP) so distinct rows written inside one
# transaction get distinct, increasing timestamps; one value feeds both columns
# so created_at == updated_at on insert.
_INSERT_ITEM = text(
    "INSERT INTO items (name, description, created_at, updated_at) "
    "SELECT :name, :description, ts, ts FROM (SELECT clock_timestamp() AS ts) AS _ts "
    "RETURNING id, name, description, created_at, updated_at"
)
_DELETE_ITEM = text("DELETE FROM items WHERE id = :id RETURNING id")


class ItemRepository(BaseRepository[ItemRead, ItemCreate, ItemUpdate]):
    """CRUD operations for the ``items`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, *, limit: int, offset: int) -> tuple[list[ItemRead], int]:
        total = await self.session.scalar(_COUNT_ITEMS)
        result = await self.session.execute(_LIST_ITEMS, {"limit": limit, "offset": offset})
        items = [ItemRead.model_validate(dict(row)) for row in result.mappings()]
        return items, int(total or 0)

    async def get(self, entity_id: uuid.UUID) -> ItemRead:
        row = (await self.session.execute(_GET_ITEM, {"id": entity_id})).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Item {entity_id} not found")
        return ItemRead.model_validate(dict(row))

    async def create(self, payload: ItemCreate) -> ItemRead:
        row = (
            (
                await self.session.execute(
                    _INSERT_ITEM,
                    {"name": payload.name, "description": payload.description},
                )
            )
            .mappings()
            .one()
        )
        return ItemRead.model_validate(dict(row))

    async def update(self, entity_id: uuid.UUID, payload: ItemUpdate) -> ItemRead:
        fields = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if key in _MUTABLE_FIELDS
        }
        if not fields:
            return await self.get(entity_id)

        # Column names come from the whitelist above; values are bound
        assignments = ", ".join(f"{column} = :{column}" for column in fields)
        statement = text(
            f"UPDATE items SET {assignments}, updated_at = clock_timestamp() "  # noqa: S608
            f"WHERE id = :id RETURNING {_COLUMNS}"
        )
        params: dict[str, Any] = {**fields, "id": entity_id}
        row = (await self.session.execute(statement, params)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Item {entity_id} not found")
        return ItemRead.model_validate(dict(row))

    async def delete(self, entity_id: uuid.UUID) -> None:
        result = await self.session.execute(_DELETE_ITEM, {"id": entity_id})
        if result.mappings().one_or_none() is None:
            raise NotFoundError(f"Item {entity_id} not found")
