"""GET /items — list items."""

from __future__ import annotations

from core.pagination import Page, PaginationDep
from items.dependencies import ItemServiceDep
from items.models import ItemRead


async def list_items(service: ItemServiceDep, pagination: PaginationDep) -> Page[ItemRead]:
    items, total = await service.list(limit=pagination.limit, offset=pagination.offset)
    return Page[ItemRead](
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )
