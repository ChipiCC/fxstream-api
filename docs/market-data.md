# Market Data

## Rates

`GET /v1/rates?symbols=EUR/USD,BTC/USDT` returns the latest cached rate per
symbol. Omit `symbols` to return every configured pair the process has seen.

```json
[
  {
    "symbol": "BTC/USDT",
    "price": "100.1",
    "source": "binance",
    "as_of": "2026-10-26T12:00:00Z",
    "stale": false
  }
]
```

- `price` is the midpoint and is serialized as a string.
- Unknown or malformed symbols return `422` with `unknown_symbol`.
- A configured symbol with no received tick yet is omitted.

### Staleness

`RateStore` computes `stale` from the tick's `as_of` timestamp and the
provider's configured threshold:

```text
PROVIDER_STALE_SECONDS={"binance":10,"frankfurter":129600}
```

Binance is real-time; Frankfurter publishes daily reference rates, so its
threshold is measured in hours. Using one global threshold would mark healthy
Frankfurter data stale (or hide a dead Binance feed).

## Quotes

`POST /v1/quotes` issues an immutable quote:

```json
{"symbol": "BTC/USDT", "side": "buy", "amount": "0.01"}
```

```json
{
  "quote_id": "6f1c1f34-7d48-4f3e-9c0f-5c9b1f0f4b7a",
  "symbol": "BTC/USDT",
  "side": "buy",
  "bid": "100.04995",
  "ask": "100.15005",
  "mid": "100.1",
  "price": "100.15005",
  "amount": "0.01",
  "spread_bps": 10,
  "issued_at": "2026-10-26T12:00:00Z",
  "expires_at": "2026-10-26T12:00:30Z"
}
```

- `spread_bps` is the total spread. The engine applies half to each side:
  `bid = mid * (1 - spread_bps / 20000)`,
  `ask = mid * (1 + spread_bps / 20000)`.
- `price` is the executable side: ask for `buy`, bid for `sell`.
- Quotes never change. They expire after `QUOTE_TTL_SECONDS` (default 30).
- `GET /v1/quotes/{quote_id}` returns the quote plus `valid`; expired quotes are
  retained for `QUOTE_RETENTION_SECONDS` so clients can observe `valid: false`.
- A stale underlying rate is rejected with `409 stale_rate`; a missing rate is
  `503 rate_unavailable`.
- The store is in memory and process-local. Quotes are not persisted for audit.

## Candles

`GET /v1/rates/{base}/{quote}/candles?interval=1m&limit=100` returns ascending
1-minute OHLC candles.

- Only `1m` is supported.
- `open`/`high`/`low`/`close` come from `Tick.last`.
- `volume` is `null`: Binance `bookTicker` and Frankfurter do not provide trade
  volume. A future trade-stream adapter can populate it.
- Buckets are keyed by `as_of` floored to the minute. Late ticks are ignored.
- Closed candles are flushed periodically and on shutdown. Writes use
  `ON CONFLICT` so a restart cannot duplicate a bucket.

## Precision

`PRICE_DECIMALS` sets the default quote precision; `PRICE_DECIMALS_BY_SYMBOL`
overrides it per pair. API values are JSON strings with trailing zeros trimmed.
Candle values are stored as `NUMERIC(30, 12)` in Postgres.
