"""Quote request and response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from market.models import Money, Side, Symbol


class QuoteCreate(BaseModel):
    """Request to issue a quote for a symbol."""

    symbol: Symbol
    side: Side
    amount: Decimal | None = Field(default=None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={"example": {"symbol": "BTC/USDT", "side": "buy", "amount": "0.01"}}
    )


class Quote(BaseModel):
    """An immutable, expiring quote."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "quote_id": "6f1c1f34-7d48-4f3e-9c0f-5c9b1f0f4b7a",
                "symbol": "BTC/USDT",
                "side": "buy",
                "bid": "65000.00",
                "ask": "65032.50",
                "mid": "65016.25",
                "price": "65032.50",
                "amount": "0.01",
                "spread_bps": 10,
                "issued_at": "2026-10-26T12:00:00Z",
                "expires_at": "2026-10-26T12:00:30Z",
            }
        },
    )

    quote_id: uuid.UUID
    symbol: Symbol
    side: Side
    bid: Money
    ask: Money
    mid: Money
    price: Money
    amount: Money | None = None
    spread_bps: int = Field(ge=0)
    issued_at: datetime
    expires_at: datetime


class QuoteStatus(Quote):
    """A quote plus whether it can still be used."""

    valid: bool
