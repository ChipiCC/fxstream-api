"""Async database engine and session management.

``get_session`` is the unit-of-work boundary: it rolls back on error and commits
on success, so a request's writes are atomic. Repositories therefore do **not**
commit — see ``docs/database.md``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

settings = get_settings()

_server_settings: dict[str, str] = {"application_name": settings.app_name}
if settings.db_statement_timeout_ms > 0:
    _server_settings["statement_timeout"] = str(settings.db_statement_timeout_ms)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo or settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_timeout=settings.db_pool_timeout_seconds,
    connect_args={"server_settings": _server_settings},
)

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session bound to one transaction.

    The transaction commits when the request completes successfully and rolls
    back if it raises, making multi-step service operations atomic.
    """
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def dispose_engine() -> None:
    """Dispose of the connection pool (called on shutdown)."""
    await engine.dispose()
