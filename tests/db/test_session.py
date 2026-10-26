"""Tests for the unit-of-work session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import db.session as session_module
from db.session import get_session


@pytest.fixture
def patched_factory(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point ``get_session`` at the test database."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "SessionFactory", factory)
    yield


async def test_get_session_commits_on_success(patched_factory: None) -> None:
    agen = cast(AsyncGenerator[AsyncSession], get_session())
    session = await agen.__anext__()
    await session.execute(text("SELECT 1"))

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()


async def test_get_session_rolls_back_on_error(patched_factory: None) -> None:
    agen = cast(AsyncGenerator[AsyncSession], get_session())
    await agen.__anext__()

    with pytest.raises(RuntimeError, match="boom"):
        await agen.athrow(RuntimeError("boom"))
