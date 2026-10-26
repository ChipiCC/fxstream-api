"""Generic persistence contract for the repository (database-access) layer.

A repository owns one entity's reads and writes. Concrete repositories
implement this contract against a backend: Postgres via hand-written SQL in a
domain (e.g. ``items/repository.py``), or an in-memory fake in the tests. The
transaction boundary is owned by the session dependency, not the repository —
see ``docs/database.md``.

The contract is backend-agnostic (the in-memory test double satisfies it with no
database at all), so it lives with the other cross-cutting abstractions in
``core`` rather than in the concrete infrastructure package ``db``.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel


class BaseRepository[TRead: BaseModel, TCreate: BaseModel, TUpdate: BaseModel](ABC):
    """Generic CRUD contract implemented by every domain repository."""

    @abstractmethod
    async def list(self, *, limit: int, offset: int) -> tuple[list[TRead], int]:
        """Return a page of entities and the total row count."""

    @abstractmethod
    async def get(self, entity_id: uuid.UUID) -> TRead:
        """Return a single entity, or raise :class:`NotFoundError`."""

    @abstractmethod
    async def create(self, payload: TCreate) -> TRead:
        """Persist a new entity and return it."""

    @abstractmethod
    async def update(self, entity_id: uuid.UUID, payload: TUpdate) -> TRead:
        """Apply a partial update and return the entity, or raise :class:`NotFoundError`."""

    @abstractmethod
    async def delete(self, entity_id: uuid.UUID) -> None:
        """Delete an entity, or raise :class:`NotFoundError`."""
