# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.
Keep this file up to date when conventions, commands, or structure change.

## Project overview

**FXStream API** ingests FX and crypto prices from external providers, normalizes
them, and serves them over REST and WebSocket. It also issues short-lived quotes
with a spread and a 30-second TTL.

The service is a **modular monolith**. It runs as a single process and keeps the
latest rate, quote, and provider state in memory. Candles are the only durable
domain and are stored in PostgreSQL.

Read [`docs/high-level-design.md`](docs/high-level-design.md) before changing
the product behaviour.

## Scope

In scope:

- Binance WebSocket ingestion and Frankfurter REST polling.
- Latest rate cache with a per-provider staleness flag.
- Subscription-based WebSocket price stream.
- REST rate snapshots, historical 1-minute candles, quotes, and provider status.
- Quote generation with bid, ask, spread, and expiry.

Out of scope for now:

- Trade execution or fund movement.
- Full user authentication.
- Equities or exchange-traded stock data.
- Redis or another external event bus.

## Setup

```bash
mise install        # provisions Python 3.15 + uv
mise run sync       # creates .venv and installs all dependency groups
cp .env.local.example .env.local
```

Never assume a globally installed `uv`/`python`; always go through `mise run …`
or `uv run …` so the correct versions are used.

## Commands

| Purpose | mise | direct |
| --- | --- | --- |
| Install deps | `mise run sync` | `uv sync --all-groups` |
| Dev server (reload) | `mise run dev` | `uv run uvicorn app:app --reload` |
| Lint | `mise run lint` | `uv run ruff check .` |
| Format | `mise run format` | `uv run ruff format .` |
| Autofix | `mise run fix` | `uv run ruff check --fix . && uv run ruff format .` |
| Type check | `mise run typecheck` | `uv run mypy src tests` |
| Tests | `mise run test` | `uv run pytest` |
| All checks | `mise run check` | — |
| New migration | `mise run revision "msg"` | `uv run alembic revision -m "msg"` |
| Apply migrations | `mise run migrate` | `uv run alembic upgrade head` |
| Start/stop Postgres | `mise run db:up` / `db:down` | `docker compose up -d db` |
| Compose up/down | `mise run docker:up` / `docker:down` | `docker compose …` |

**Definition of done:** `mise run check` passes (lint + mypy + tests), and a
raw-SQL migration exists for any schema change.

## Architecture

```
Providers → Normalizer → Rate Store → Event Bus → WebSocket Gateway
                                │           │
                                │           └→ Candle Aggregator → PostgreSQL
                                └→ Quote Engine → in-memory Quote Store
```

```
src/
├── app.py                 # app factory, lifespan, router wiring
├── core/                  # config, logging, errors, middleware, metrics, clock
├── db/                    # async engine + request/background sessions
├── market/                # Tick/Rate models, RateStore, EventBus, runtime container
├── providers/             # RateProvider adapters, normalizers, registry, status API
├── rates/                 # REST rate snapshot + candles endpoints
├── quotes/                # Quote engine, in-memory store, REST API
├── candles/               # OHLC aggregation, PostgreSQL repository
├── streaming/             # WebSocket gateway and subscription backpressure
└── internal/              # metadata and health probes
```

The source root is `src/`, a flat namespace — imports are absolute from the top
level (`core.config`, `market.rate_store`, `app`). There is no `app/` package.

### Data flow

1. A provider adapter receives a payload and normalizes it into a `Tick`.
2. `RateStore` stores the latest tick per symbol and computes staleness.
3. `EventBus` offers the tick to every matching subscription.
4. The WebSocket gateway sends the latest tick per symbol to each client.
5. The candle aggregator builds 1-minute candles and flushes them to Postgres.
6. `QuoteEngine` reads the latest non-stale rate, applies the spread, and stores
   an immutable quote with an expiry.

## Hard invariants

- **Decimal only.** Never use `float` for prices, spreads, or amounts. Parse
  provider strings into `Decimal`; serialize prices and quantities as strings.
- **UTC only.** All timestamps are timezone-aware UTC. Use the injected `Clock`
  for expiry and staleness; do not call `datetime.now()` in domain code.
- **Quotes are immutable.** Once issued they never change. They expire; they are
  never updated. The quote store is in memory and single-process.
- **Stale rates cannot be quoted.** Reject with an explicit `stale_rate` error.
  Never silently use an old price.
- **The event bus never blocks.** A slow WebSocket client may lose intermediate
  ticks; it must always keep the latest tick per symbol.
- **Ingestion is isolated from failures.** A provider disconnect, malformed
  payload, or database error must not crash the app or stop other providers.
- **Provider adapters own their protocol.** Business logic never parses Binance
  or Frankfurter payloads. Normalizers are pure functions and unit-tested.
- **Background writes own their session.** The candle aggregator opens its own
  session and commits; request-scoped sessions are never reused in tasks.
- **No ORM.** All SQL is hand-written and parameterized through
  `sqlalchemy.text()`. No `DeclarativeBase`, `Mapped`, or autogenerate.
- **Single-process state.** Rates, quotes, and provider status are not shared
  across workers. Document the Redis upgrade path instead of assuming it works.

## Domain conventions

### Market models

`market/models.py` owns the shared `Tick`, `Rate`, `Candle`, and provider enums.
Symbols use `BASE/QUOTE` (e.g. `EUR/USD`, `BTC/USDT`) and are normalized to
uppercase. Validate symbols at API boundaries and at startup.

### Providers

Every provider implements `RateProvider` from `providers/base.py`:

- `run(sink: TickSink)` connects/polls until stopped and emits ticks through the
  provided sink.
- `status()` returns a `ProviderStatus`.
- `stop()` requests shutdown and closes owned resources.

Shared resilience lives in `BaseProvider`: exponential backoff, a circuit
breaker (`up` → `degraded` → `down`), reconnect counts, and provider metrics.
Provider-specific payload parsing lives in `providers/normalizer.py`.

Add a provider by:

1. Adding config fields and `.env.local.example` entries.
2. Writing a normalizer with fixture-driven unit tests.
3. Subclassing `BaseProvider`, implementing the protocol loop, and emitting
   normalized ticks.
4. Registering it in `providers/registry.py`.
5. Adding status/config/API tests. Never call live providers in tests.

### Rates and quotes

- `RateStore` is the only source of the latest price. It computes `Rate.price`
  as the midpoint and `Rate.stale` from `as_of` and the provider threshold.
- `QuoteEngine` applies a **half-spread per side**:
  `bid = mid * (1 - spread_bps / 20000)`,
  `ask = mid * (1 + spread_bps / 20000)`.
- Quantize with the configured symbol precision. Use `Decimal` rounding, never
  binary floats.
- `QuoteStore` retains expired quotes for a short grace period so `GET` can
  return `valid: false`; then evicts them.

### Candles

- Only the `1m` interval is supported.
- Bucket ticks by `as_of` floored to the minute. Ignore ticks older than the
  current bucket.
- `open`/`high`/`low`/`close` come from `Tick.last`; `volume` is `None` because
  neither current provider supplies trade volume.
- Flush closed candles periodically and on shutdown. Use an upsert so a restart
  cannot duplicate a candle.
- Database columns are `open_price`, `high_price`, `low_price`, `close_price`;
  map them to the API's `open`, `high`, `low`, `close` fields.

## API conventions

- Public market data lives under `/v1` (the HLD contract). Internal probes stay
  at the root.
- `GET /health` is the aggregate health endpoint; keep `/health/live` and
  `/health/ready` for orchestrators.
- Error envelopes are produced by `core/exceptions.py`:
  `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- Prices and quantities are JSON strings. Return ISO-8601 UTC timestamps.
- Quote routes use the optional API-key guard; rates and WebSocket are public.
- WebSocket messages are JSON. Subscribe/unsubscribe actions are documented in
  `docs/websocket.md`.

## Configuration

- Add settings to `Settings` in `core/config.py` with a safe default.
- Add every setting to `.env.local.example` and the table in
  `docs/configuration.md`.
- Read settings through `get_settings()`; never call `os.environ` directly.
- `.env.local` is gitignored and must never be committed or exposed.
- Per-provider staleness thresholds are mandatory; a single global threshold is
  wrong because Binance is real-time and Frankfurter is daily.

## Observability

- Use `get_logger(__name__)` (structlog). Include `source`, `symbol`, and
  `latency_ms` where relevant.
- Provider metrics use the `fxstream_` prefix:
  messages, errors, reconnects, state, last message timestamp.
- WebSocket metrics: subscriber count and sent/coalesced messages.
- Quote metrics: request outcomes and generation latency.
- Never log secrets or raw `.env.local` values.

## Testing

- Tests live in `tests/`, mirroring the package layout.
- Tests run against a **real PostgreSQL database** for DB code. Start it with
  `mise run db:up`.
- **No live network.** Use fake providers, `httpx.MockTransport`, and fake
  WebSocket connections. Provider adapters must accept injected clients.
- Use a fake clock for quote expiry and staleness. No `sleep`-based assertions.
- Cover happy paths and error paths: stale rate, missing rate, invalid symbol,
  expired quote, provider failure, malformed payload, WS backpressure.
- `pytest-asyncio` is in `auto` mode — write plain `async def test_...`.
- The schema is built from Alembic migrations in a subprocess; keep migrations
  reversible and test the migration upgrade/downgrade path.
- Warnings are errors (`filterwarnings = error`); do not introduce warnings.
- Coverage is enforced at 90%. Do not lower `fail_under`. The coverage config
  must keep `concurrency = ["greenlet", "thread"]`; do not remove it.

## Migrations

- `target_metadata = None`; autogenerate is disabled.
- `mise run revision "msg"` creates an empty migration. Fill `upgrade()` and
  `downgrade()` with raw SQL via `op.execute(...)`.
- The migration is the source of truth for the schema.
- Filenames are timestamped `year_month_day_HMS` via `alembic.ini`.

## Agent tooling

This repo ships project-specific OpenCode configuration:

- `.opencode/opencode.json` — permissions, instructions, watcher, default agent.
- `.opencode/commands/` — `/check`, `/new-domain`, `/new-provider`, `/review`,
  `/smoke`.
- `.opencode/agents/fxstream-reviewer.md` — read-only review subagent focused on
  the invariants above.

Use the reviewer before large merges. Keep commands and AGENTS.md in sync when
the workflow changes.

## Do not

- Do not use `float` for prices, amounts, or spreads.
- Do not call provider HTTP/WebSocket endpoints from tests.
- Do not block the event bus or await slow client I/O inside `publish`.
- Do not let a provider exception crash the application or other providers.
- Do not bypass the service/engine layer from a handler.
- Do not edit `.env.local`, `.venv/`, or `uv.lock` by hand.
- Do not add dependencies without updating `uv.lock` (`uv add <pkg>`).
- Do not weaken Ruff, mypy, coverage, or the warnings-as-errors policy.
- Do not add narration comments that restate the code.
- Do not commit real secrets or generated caches.

## Environment

- Python ≥ 3.15. Tool versions pinned in `mise.toml`.
- Source root: `src/`; packaging via `hatchling`.
- Tests set `pythonpath = ["src"]`.
- Tests disable live ingestion with `MARKET_DATA_ENABLED=false`.
