"""Quote generation with Decimal spreads and injectable expiry."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from core.clock import Clock
from core.exceptions import NotFoundError, RateUnavailableError, StaleRateError
from core.metrics import QUOTE_DURATION, QUOTE_REQUESTS
from core.symbols import normalize_symbol
from market.models import Side
from market.rate_store import RateStore
from quotes.models import Quote, QuoteCreate, QuoteStatus
from quotes.store import QuoteStore

_BPS_DENOMINATOR = Decimal(20000)


class QuoteEngine:
    """Create immutable quotes from the latest non-stale market rate."""

    def __init__(
        self,
        *,
        rate_store: RateStore,
        store: QuoteStore,
        clock: Clock,
        spreads: Mapping[str, int] | None = None,
        default_spread_bps: int = 10,
        price_decimals: int = 8,
        price_decimals_by_symbol: Mapping[str, int] | None = None,
        ttl_seconds: int = 30,
    ) -> None:
        self._rate_store = rate_store
        self._store = store
        self._clock = clock
        self._spreads = dict(spreads or {})
        self._default_spread = default_spread_bps
        self._price_decimals = price_decimals
        self._price_decimals_by_symbol = dict(price_decimals_by_symbol or {})
        self._ttl = timedelta(seconds=ttl_seconds)

    def create(self, request: QuoteCreate) -> Quote:
        started = time.perf_counter()
        symbol = normalize_symbol(request.symbol)
        rate = self._rate_store.get(symbol)
        if rate is None:
            QUOTE_REQUESTS.labels(outcome="unavailable").inc()
            QUOTE_DURATION.observe(time.perf_counter() - started)
            raise RateUnavailableError(f"No rate is available for {symbol}")

        if rate.stale:
            QUOTE_REQUESTS.labels(outcome="stale").inc()
            QUOTE_DURATION.observe(time.perf_counter() - started)
            raise StaleRateError(
                f"Rate for {symbol} is stale",
                details={"symbol": symbol, "as_of": rate.as_of.isoformat()},
            )

        tick = self._rate_store.latest_tick(symbol)
        if tick is None:  # defensive: rate and tick are written together
            QUOTE_REQUESTS.labels(outcome="unavailable").inc()
            QUOTE_DURATION.observe(time.perf_counter() - started)
            raise RateUnavailableError(f"No rate is available for {symbol}")

        mid = (tick.bid + tick.ask) / 2
        spread_bps = self._spreads.get(symbol, self._default_spread)
        half_spread = Decimal(spread_bps) / _BPS_DENOMINATOR
        quantum = Decimal(1).scaleb(-self._price_decimals_for(symbol))
        bid = (mid * (1 - half_spread)).quantize(quantum, rounding=ROUND_HALF_UP)
        ask = (mid * (1 + half_spread)).quantize(quantum, rounding=ROUND_HALF_UP)
        issued_at = self._clock.now()
        price = ask if request.side is Side.BUY else bid

        quote = Quote(
            quote_id=uuid.uuid4(),
            symbol=symbol,
            side=request.side,
            bid=bid,
            ask=ask,
            mid=mid.quantize(quantum, rounding=ROUND_HALF_UP),
            price=price,
            amount=request.amount,
            spread_bps=spread_bps,
            issued_at=issued_at,
            expires_at=issued_at + self._ttl,
        )
        self._store.put(quote)
        QUOTE_REQUESTS.labels(outcome="success").inc()
        QUOTE_DURATION.observe(time.perf_counter() - started)
        return quote

    def get(self, quote_id: uuid.UUID) -> QuoteStatus:
        quote = self._store.get(quote_id)
        if quote is None:
            raise NotFoundError(f"Quote {quote_id} not found")
        return QuoteStatus(
            **quote.model_dump(),
            valid=self._clock.now() < quote.expires_at,
        )

    def _price_decimals_for(self, symbol: str) -> int:
        return self._price_decimals_by_symbol.get(symbol, self._price_decimals)
