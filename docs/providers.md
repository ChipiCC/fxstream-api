# Providers

Two adapters ship by default:

| Provider | Transport | Symbols | Staleness default |
| --- | --- | --- | --- |
| Binance | WebSocket `bookTicker` | crypto pairs (`BTC/USDT`) | 10 seconds |
| Frankfurter | HTTP `/latest` polling | FX pairs (`EUR/USD`) | 36 hours |

Both implement `RateProvider` from
[`src/providers/base.py`](../src/providers/base.py) and emit normalized `Tick`
models. Payload parsing lives in
[`src/providers/normalizer.py`](../src/providers/normalizer.py) as pure
functions.

## Binance

- Builds a combined stream URL: `wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker`.
- Maps `BTC/USDT` to `BTCUSDT`; `last` is the bid/ask midpoint.
- Uses local receive time because `bookTicker` has no event timestamp.
- Malformed messages are logged, counted, and skipped; the connection stays up.

## Frankfurter

- Polls `https://api.frankfurter.dev/v1/latest?from=EUR&to=USD,GBP`, grouped by
  base currency.
- The reference date is treated as midnight UTC; the per-provider staleness
  threshold should account for weekends and publication delays.
- Since Frankfurter publishes a single reference rate, `bid = ask = last`.

## Resilience

`BaseProvider` owns:

- exponential backoff between attempts (`PROVIDER_BACKOFF_*`);
- a circuit breaker: `up` → `degraded` → `down` after
  `PROVIDER_FAILURE_THRESHOLD` consecutive failures;
- reconnect counts and last-message timestamps exposed by
  `GET /v1/providers/status`;
- provider metrics (`fxstream_provider_*`).

Provider failures are isolated: a crashing task cannot stop the app or other
providers.

## Adding a provider

1. Add settings: symbols, endpoint, poll/connection options, staleness, timeout.
2. Add a normalizer and fixture-driven unit tests.
3. Subclass `BaseProvider`, implement `_run(sink)`, and emit ticks with
   `_emit`. Reuse the inherited backoff/status behavior.
4. Register the adapter in `providers/registry.py`.
5. Add config, malformed-payload, and failure tests. No live network.
6. Update this page, `docs/configuration.md`, and `.env.local.example`.

## Configuration

```bash
BINANCE_SYMBOLS=BTC/USDT
FRANKFURTER_SYMBOLS=EUR/USD
BINANCE_WS_URL=wss://stream.binance.com:9443/stream
FRANKFURTER_BASE_URL=https://api.frankfurter.dev/v1
FRANKFURTER_POLL_SECONDS=3600
PROVIDER_REQUEST_TIMEOUT_SECONDS=10
PROVIDER_STALE_SECONDS={"binance":10,"frankfurter":129600}
PROVIDER_FAILURE_THRESHOLD=3
PROVIDER_BACKOFF_INITIAL_SECONDS=1
PROVIDER_BACKOFF_MAX_SECONDS=60
MARKET_DATA_ENABLED=true
```

A symbol can belong to only one provider; startup validation rejects overlap.
