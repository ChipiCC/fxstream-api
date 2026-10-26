"""Native SQL repository for candles."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from market.models import Candle

_UPSERT_CANDLE = text(
    """
    INSERT INTO candles (
        symbol, interval_code, open_time,
        open_price, high_price, low_price, close_price, volume
    )
    VALUES (
        :symbol, :interval, :open_time,
        :open, :high, :low, :close, :volume
    )
    ON CONFLICT (symbol, interval_code, open_time)
    DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        volume = EXCLUDED.volume
    """
)

_LIST_CANDLES = text(
    """
    SELECT
        symbol,
        interval_code AS interval,
        open_time,
        open_price AS open,
        high_price AS high,
        low_price AS low,
        close_price AS close,
        volume
    FROM candles
    WHERE symbol = :symbol AND interval_code = :interval
    ORDER BY open_time DESC
    LIMIT :limit
    """
)


class CandleRepository:
    """Read and write candles with hand-written SQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, candle: Candle) -> None:
        await self.session.execute(
            _UPSERT_CANDLE,
            {
                "symbol": candle.symbol,
                "interval": candle.interval,
                "open_time": candle.open_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            },
        )

    async def list(self, *, symbol: str, interval: str, limit: int) -> list[Candle]:
        result = await self.session.execute(
            _LIST_CANDLES,
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        candles = [Candle.model_validate(dict(row)) for row in result.mappings()]
        return list(reversed(candles))
