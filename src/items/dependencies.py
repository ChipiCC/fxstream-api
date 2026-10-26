"""Items domain dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from db.session import SessionDep
from items.repository import ItemRepository
from items.service import ItemService


def get_item_repository(session: SessionDep) -> ItemRepository:
    return ItemRepository(session)


ItemRepositoryDep = Annotated[ItemRepository, Depends(get_item_repository)]


def get_item_service(repository: ItemRepositoryDep) -> ItemService:
    return ItemService(repository)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
