# Architecture

FXStream API is a **modular monolith**. One process owns ingestion, the latest
rate cache, quote generation, WebSocket fan-out, and candle persistence.

```
Provider adapters → Normalizer → Rate Store → Event Bus → WebSocket Gateway
                                        │            │
                                        │            └→ Candle Aggregator → PostgreSQL
                                        └→ Quote Engine → in-memory Quote Store
```

## Packages

| Package | Responsibility |
| --- | --- |
| `src/market/` | `Tick`, `Rate`, `Candle`, provider enums, `RateStore`, coalescing `EventBus`, runtime container. |
| `src/providers/` | `RateProvider` contract, reconnect/backoff/circuit breaker, Binance and Frankfurter adapters, pure normalizers, registry, status API. |
| `src/rates/` | `GET /v1/rates` snapshot endpoint. |
| `src/quotes/` | Decimal quote engine, in-memory quote store, REST endpoints. |
| `src/candles/` | 1-minute OHLC aggregation, background writer, native-SQL repository, history endpoint. |
| `src/streaming/` | WebSocket subscription protocol and latest-per-symbol backpressure. |
| `src/ingestion/` | Provider task supervision and tick fan-out. |
| `src/core/` | Config, logging, errors, middleware, metrics, clock, symbol helpers. |
| `src/db/` | Async engine, request unit of work, session factory for background writers. |
| `src/internal/` | Service metadata and health probes. |

Imports are absolute from `src/` (`from market.rate_store import RateStore`).

## Request path

1. Middleware runs: request context/access log, metrics, CORS, security headers,
   trusted host, rate limiting.
2. FastAPI routes to a handler in `src/<domain>/handlers/`.
3. The handler uses a dependency from `market.dependencies` / the domain to reach
   the runtime store or engine. Handlers stay thin.
4. For candle reads, the handler calls `CandleRepository` with the request
   session. `get_session` commits on success and rolls back on error.
5. Errors become the standard `{"error": ...}` envelope from
   `core/exceptions.py`.

## Ingestion path

1. `IngestionManager` starts one task per provider plus the candle aggregator.
2. Each provider reconnects with exponential backoff and reports `up`,
   `degraded`, or `down` through `ProviderStatus`.
3. `providers/normalizer.py` turns a provider payload into a `Tick` with
   `Decimal` prices and UTC timestamps.
4. The provider calls its tick sink; `IngestionManager` updates `RateStore`,
   publishes to `EventBus`, and feeds the candle aggregator.
5. The WebSocket sender drains a coalescing buffer, so a slow client receives
   the latest tick per symbol rather than a backlog.
6. The candle aggregator flushes closed 1-minute candles using its own database
   session. A write failure is logged and retried on the next flush; ingestion
   continues.

## Runtime state

`MarketRuntime` (built in `market/runtime.py`) owns:

- `RateStore` — latest tick per symbol + staleness.
- `EventBus` — WebSocket subscriptions.
- `QuoteStore` / `QuoteEngine` — quotes and spread/expiry logic.
- `ProviderRegistry` — provider adapters and statuses.
- `CandleAggregator` — current/pending candles (optional via config).
- `IngestionManager` — lifecycle supervision.

It is stored on `app.state.market`. Tests replace it with a fresh runtime and
fake providers.

## Why no ORM

Candles are the only durable domain. SQLAlchemy is the async connection pool and
transaction manager; every statement is hand-written and parameterized. This
keeps the query surface explicit and makes the Alembic migration the single
source of truth. See [database.md](database.md).

## Single-process design

Rates, quotes, provider status, and subscriptions are process-local. Run one
worker/replica, or add a shared store/pub-sub before scaling horizontally. The
same limitation applies to the in-process rate limiter. See
[operations.md](operations.md#scaling).

## Adding a domain

1. Decide whether it persists data; if so, add a raw-SQL migration.
2. Add models in `src/<domain>/models.py`.
3. Add business logic in `engine.py` / `service.py`.
4. Add native SQL in `repository.py` when needed (no commits in repositories).
5. Add handlers, router, and dependencies; register the router in `src/app.py`.
6. Add tests under `tests/<domain>/`; no live network.
7. Update docs and AGENTS.md if conventions change.
