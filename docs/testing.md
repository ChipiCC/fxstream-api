# Testing

Tests live in `tests/` and mirror the package layout. Tests never call live
providers. Database tests run against **real PostgreSQL**; the schema is built
by applying the Alembic migrations in a subprocess, so every run exercises the
migrations too.

## Running

```bash
mise run db:up     # start Postgres
mise run test      # uv run pytest
```

The target is `TEST_DATABASE_URL`, defaulting to
`postgresql+asyncpg://postgres:postgres@localhost:5432/app_test`.

`pytest-asyncio` is in `auto` mode, so write plain `async def test_...`.
`MARKET_DATA_ENABLED=false` is set before the app is imported, so no provider
tasks start during tests.

## Layout

```text
tests/
├── conftest.py              # DB fixtures, fresh market runtime, HTTP client
├── core/                    # config, middleware, metrics, security
├── db/                      # unit-of-work session
├── internal/                # metadata + health probes
├── market/                  # models, RateStore, EventBus
├── providers/               # normalizers, adapters, resilience, status API
├── quotes/                  # engine math, expiry, REST
├── rates/                   # snapshot API
├── candles/                 # aggregator, repository, writer, API
├── streaming/               # WebSocket protocol/backpressure
├── ingestion/               # manager fan-out and failure isolation
└── helpers/fakes.py         # FakeClock, FakeProvider, FakeCandleWriter
```

## Fixtures

| Fixture | Scope | Purpose |
| --- | --- | --- |
| `database_url` | session | Migrated, empty test database (`downgrade base` → `upgrade head`). |
| `engine` | function | Async engine bound to the test database (`NullPool`). |
| `session` | function | Session on a clean schema (all tables truncated). |
| `client` | function | `httpx` ASGI client with the DB dependency overridden. |
| `market` | function | Fresh `MarketRuntime` with in-memory stores and no live providers. |

The `session` fixture truncates every table except `alembic_version`, so new
tables are isolated automatically.

## Test doubles

`tests/helpers/fakes.py` provides:

- `FakeClock` — deterministic time for quote expiry/staleness.
- `make_tick(...)` — build a validated `Tick` with sensible defaults.
- `FakeProvider` — emit fixed ticks and optionally block until stopped.
- `FakeCandleWriter` — record flushes and simulate write failures.

Provider tests inject fake WebSocket connectors and `httpx.MockTransport`.
Never use real network calls in the suite.

## What to cover

- Happy paths and error paths: stale rate, missing rate, expired quote, unknown
  symbol, invalid payload, provider failure, WS backpressure.
- Decimal spread math and price serialization as strings.
- Provider reconnect/backoff/circuit-breaker transitions.
- Candle OHLC correctness, late ticks, flush failure, upsert idempotency.
- WebSocket subscribe/unsubscribe, invalid frames, and coalescing.
- Configuration, auth, readiness, and rate-limit middleware.

## Contract tests

`tests/test_openapi.py` checks the HLD paths exist and validates documented
quote examples against the Pydantic models.

## Coverage

Coverage is enforced at 90% (`pyproject.toml`). Do not lower `fail_under`.
Keep `concurrency = ["greenlet", "thread"]` in place; SQLAlchemy async runs
through greenlet and FastAPI uses a threadpool. Without it, coverage silently
drops lines after a DB `await`.

## Warnings

`filterwarnings = ["error"]` — do not introduce new warnings.
