"""Pydantic models (request/response) for items.

Because queries return plain rows (not ORM objects), ``ItemRead`` is validated
directly from mappings produced by SQLAlchemy — see ``items/service.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Widget"])
    description: str | None = Field(default=None, examples=["A very nice widget"])


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ItemRead(ItemBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
