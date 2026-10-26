"""Offset/limit pagination: the request dependency and the response envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class Pagination:
    """Simple offset/limit pagination parameters."""

    limit: int
    offset: int


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(get_pagination)]


class Page[T](BaseModel):
    """A page of results with pagination metadata."""

    items: list[T]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
