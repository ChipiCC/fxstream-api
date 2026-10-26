# FXStream API

Real-time FX and crypto rates, 1-minute candles, and short-lived quotes.

- **Runtime:** Python 3.15, FastAPI, Uvicorn
- **Ingestion:** Binance `bookTicker` WebSocket + Frankfurter REST polling
- **Market data:** in-memory rate cache with per-provider staleness, coalescing
  WebSocket fan-out, and Decimal prices end to end
- **Quotes:** immutable, configurable spread per symbol, 30-second TTL
- **Persistence:** native SQL over async SQLAlchemy Core + asyncpg, Alembic
  raw-SQL migrations, PostgreSQL for candles (no ORM)
- **Observability:** structured JSON logs, request IDs, Prometheus metrics for
  HTTP, providers, WebSocket, and quotes
- **Quality:** Ruff, mypy strict, pytest + coverage gate, real Postgres tests
- **Ops:** Dockerfile (multi-stage, non-root), Docker Compose, GitHub Actions CI

Read the [high-level design](docs/high-level-design.md) for product scope and the
full component model.

## Documentation

Full documentation lives in [`docs/`](docs/README.md):

| Topic | Description |
| --- | --- |
| [High-Level Design](docs/high-level-design.md) | Scope, components, data model, API contract |
| [Architecture](docs/architecture.md) | Runtime flow, packages, and invariants |
| [Configuration](docs/configuration.md) | Every setting and production validation |
| [Market Data](docs/market-data.md) | Rates, quotes, candles, and staleness |
| [Providers](docs/providers.md) | Binance, Frankfurter, resilience, adding a provider |
| [WebSocket](docs/websocket.md) | Subscription protocol and backpressure |
| [Authentication](docs/authentication.md) | Optional API-key auth |
| [CORS](docs/cors.md) | Browser cross-origin setup |
| [Security](docs/security.md) | Headers, trusted hosts, rate limiting |
| [Metrics](docs/metrics.md) | Prometheus instruments |
| [Observability](docs/observability.md) | Logging, request IDs, tracing roadmap |
| [Database](docs/database.md) | Native SQL, transactions, candle schema |
| [Testing](docs/testing.md) | Fixtures, fakes, coverage |
| [Operations](docs/operations.md) | Docker, migrations, health, shutdown |
| [Roadmap](docs/roadmap.md) | Deliberately out-of-scope items |

## Architecture

```
Providers → Normalizer → Rate Store → Event Bus → WebSocket Gateway
                                │           │
                                │           └→ Candle Aggregator → PostgreSQL
                                └→ Quote Engine → in-memory Quote Store
```

```text
src/
├── app.py                 # app factory, lifespan, router wiring
├── core/                  # config, logging, errors, middleware, metrics, clock
├── db/                    # async engine + request/background sessions
├── market/                # Tick/Rate models, RateStore, EventBus, runtime
├── providers/             # Binance, Frankfurter, normalizers, status API
├── rates/                 # REST rate snapshots
├── quotes/                # quote engine, in-memory store, REST API
├── candles/               # OHLC aggregation, PostgreSQL repository
├── streaming/             # WebSocket gateway and backpressure
└── internal/              # metadata and health probes
```

**Invariants:** Decimal only, UTC only, immutable quotes, stale rates rejected,
non-blocking event bus, provider failures isolated, native parameterized SQL.
See [`AGENTS.md`](AGENTS.md) for the full rule set.

## Getting started

```bash
mise install        # install Python 3.15 + uv
mise run sync       # create .venv and install dependencies
cp .env.local.example .env.local
mise run db:up      # start Postgres (Docker Compose)
mise run migrate    # apply migrations
mise run dev        # http://localhost:8000/docs
```

The service starts ingesting by default. Set `MARKET_DATA_ENABLED=false` to run
without live providers (for example while working offline).

Run the whole stack with Docker:

```bash
mise run docker:up
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Service metadata |
| `GET` | `/health` | Aggregate health (database readiness) |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe |
| `GET` | `/metrics` | Prometheus metrics (when enabled) |
| `GET` | `/v1/rates?symbols=EUR/USD,BTC/USDT` | Latest rate snapshot |
| `GET` | `/v1/rates/{base}/{quote}/candles?interval=1m&limit=100` | Historical candles |
| `POST` | `/v1/quotes` | Create an expiring quote |
| `GET` | `/v1/quotes/{quote_id}` | Fetch a quote and its validity |
| `GET` | `/v1/providers/status` | Provider state |
| `WS` | `/v1/ws/rates` | Subscribe to rate ticks |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | API docs |

Quote routes accept the `X-API-Key` header when `API_KEYS` is configured. Rates
and WebSocket market data are public.

## Configuration

All settings live in [`src/core/config.py`](src/core/config.py) and are read from
environment variables (plus `.env.local` outside production). See
[`.env.local.example`](.env.local.example) and
[`docs/configuration.md`](docs/configuration.md).

Key defaults:

```bash
BINANCE_SYMBOLS=BTC/USDT
FRANKFURTER_SYMBOLS=EUR/USD
PROVIDER_STALE_SECONDS={"binance":10,"frankfurter":129600}
DEFAULT_SPREAD_BPS=10
QUOTE_TTL_SECONDS=30
```

## Testing

Tests run against a **real PostgreSQL database** (no SQLite). Start one with
`mise run db:up`, then:

```bash
mise run test
```

The connection comes from `TEST_DATABASE_URL` (default
`postgresql+asyncpg://postgres:postgres@localhost:5432/app_test`). Tests disable
live ingestion, inject fake providers/clocks, and never call Binance or
Frankfurter. Coverage is enforced at 90%. See
[`docs/testing.md`](docs/testing.md).

## Single-process note

Rates, quotes, provider state, and WebSocket subscriptions live in memory. Run
one worker per process group, or add a shared store (Redis/pub-sub) before
scaling horizontally. See [`docs/operations.md`](docs/operations.md#scaling).

## License

MIT — see [LICENSE](LICENSE).
