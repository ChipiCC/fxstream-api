"""Domain models shared by ingestion, rates, quotes, candles, and streaming."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from core.symbols import normalize_symbol


def _normalize_symbol(value: str) -> str:
    return normalize_symbol(value)


Symbol = Annotated[str, BeforeValidator(_normalize_symbol)]


def _serialize_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


Money = Annotated[
    Decimal,
    PlainSerializer(_serialize_decimal, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class ProviderState(StrEnum):
    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"


class Tick(BaseModel):
    """A normalized price update from one provider."""

    model_config = ConfigDict(frozen=True)

    symbol: Symbol
    bid: Decimal
    ask: Decimal
    last: Decimal
    source: str = Field(min_length=1)
    as_of: datetime
    received_at: datetime

    @field_validator("bid", "ask", "last")
    @classmethod
    def _positive_prices(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("prices must be positive")
        return value

    @field_validator("as_of", "received_at")
    @classmethod
    def _utc_timestamps(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _ordered_quotes(self) -> Tick:
        if self.bid > self.ask:
            raise ValueError("bid cannot be greater than ask")
        return self


class Rate(BaseModel):
    """The latest public rate snapshot for a symbol."""

    model_config = ConfigDict(frozen=True)

    symbol: Symbol
    price: Money
    source: str
    as_of: datetime
    stale: bool


class Candle(BaseModel):
    """A closed OHLC candle."""

    model_config = ConfigDict(frozen=True)

    symbol: Symbol
    interval: str
    open_time: datetime
    open: Money
    high: Money
    low: Money
    close: Money
    volume: Decimal | None = None

    @field_validator("open_time")
    @classmethod
    def _utc_open_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("open_time must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _positive_prices(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("prices must be positive")
        return value

    @model_validator(mode="after")
    def _valid_range(self) -> Candle:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC range")
        if self.high < self.low:
            raise ValueError("high cannot be below low")
        return self


class ProviderStatus(BaseModel):
    """Observable state of one market data provider."""

    name: str
    state: ProviderState
    last_message_at: datetime | None = None
    reconnects: int = Field(default=0, ge=0)
