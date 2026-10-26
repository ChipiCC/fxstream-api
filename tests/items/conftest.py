"""Items-domain test fixtures.

``item_repository`` is parametrized so the CRUD suite runs against both the
Postgres repository and the in-memory test double.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from items.models.item import ItemCreate, ItemRead, ItemUpdate
from items.repository import ItemRepository
from tests.helpers.repositories import InMemoryItemRepository


@pytest.fixture(params=["in_memory", "postgres"])
async def item_repository(
    request: pytest.FixtureRequest, session: AsyncSession
) -> AsyncIterator[BaseRepository[ItemRead, ItemCreate, ItemUpdate]]:
    if request.param == "postgres":
        yield ItemRepository(session)
    else:
        yield InMemoryItemRepository()
