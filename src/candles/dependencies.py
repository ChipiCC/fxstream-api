"""Candle dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from candles.repository import CandleRepository
from db.session import SessionDep


def get_candle_repository(session: SessionDep) -> CandleRepository:
    return CandleRepository(session)


CandleRepositoryDep = Annotated[CandleRepository, Depends(get_candle_repository)]
