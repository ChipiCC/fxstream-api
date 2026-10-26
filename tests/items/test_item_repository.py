"""CRUD contract tests for the item repositories.

Each test runs against both the Postgres ``ItemRepository`` and the in-memory
test double (see ``tests/items/conftest.py``), so the two implementations are
held to the same behaviour.
"""

from __future__ import annotations

import uuid

import pytest

from core.exceptions import NotFoundError
from core.repository import BaseRepository
from items.models import ItemCreate, ItemRead, ItemUpdate


async def test_create_returns_persisted_item(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    item = await item_repository.create(ItemCreate(name="Widget", description="nice"))

    assert isinstance(item.id, uuid.UUID)
    assert item.name == "Widget"
    assert item.description == "nice"
    assert item.created_at is not None
    assert item.updated_at == item.created_at


async def test_get_returns_created_item(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    created = await item_repository.create(ItemCreate(name="Widget"))

    fetched = await item_repository.get(created.id)
    assert fetched == created


async def test_get_missing_raises_not_found(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    with pytest.raises(NotFoundError):
        await item_repository.get(uuid.uuid4())


async def test_list_returns_page_and_total(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    for i in range(3):
        await item_repository.create(ItemCreate(name=f"item-{i}"))

    items, total = await item_repository.list(limit=2, offset=0)
    assert total == 3
    assert len(items) == 2


async def test_list_orders_by_created_at_desc(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    first = await item_repository.create(ItemCreate(name="first"))
    second = await item_repository.create(ItemCreate(name="second"))

    items, _ = await item_repository.list(limit=10, offset=0)
    assert [item.id for item in items] == [second.id, first.id]


async def test_list_applies_offset(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    for i in range(3):
        await item_repository.create(ItemCreate(name=f"item-{i}"))

    items, total = await item_repository.list(limit=10, offset=2)
    assert total == 3
    assert len(items) == 1


async def test_list_empty(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    items, total = await item_repository.list(limit=10, offset=0)
    assert items == []
    assert total == 0


async def test_update_changes_fields(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    created = await item_repository.create(ItemCreate(name="old", description="keep"))

    updated = await item_repository.update(created.id, ItemUpdate(name="new"))
    assert updated.id == created.id
    assert updated.name == "new"
    assert updated.description == "keep"
    assert updated.updated_at >= created.updated_at


async def test_update_empty_payload_returns_item(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    created = await item_repository.create(ItemCreate(name="stable"))

    updated = await item_repository.update(created.id, ItemUpdate())
    assert updated.name == "stable"


async def test_update_missing_raises_not_found(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    with pytest.raises(NotFoundError):
        await item_repository.update(uuid.uuid4(), ItemUpdate(name="new"))


async def test_delete_removes_item(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    created = await item_repository.create(ItemCreate(name="temp"))

    await item_repository.delete(created.id)

    with pytest.raises(NotFoundError):
        await item_repository.get(created.id)


async def test_delete_missing_raises_not_found(
    item_repository: BaseRepository[ItemRead, ItemCreate, ItemUpdate],
) -> None:
    with pytest.raises(NotFoundError):
        await item_repository.delete(uuid.uuid4())
