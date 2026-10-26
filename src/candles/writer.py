"""Background candle writer that owns its database sessions."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from candles.repository import CandleRepository
from db.session import SessionFactory
from market.models import Candle


class CandleWriter:
    """Persist candles outside the request lifecycle."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or SessionFactory

    async def write(self, candles: Sequence[Candle]) -> None:
        if not candles:
            return
        async with self._session_factory() as session:
            repository = CandleRepository(session)
            for candle in candles:
                await repository.upsert(candle)
            await session.commit()
