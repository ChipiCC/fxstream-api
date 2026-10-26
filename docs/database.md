# Database

FXStream persists **1-minute candles** only. Rates, quotes, provider state, and
WebSocket subscriptions live in memory.

Persistence is **native SQL over async SQLAlchemy Core + asyncpg**. SQLAlchemy is
the async connection pool and transaction manager; there is no ORM and no
autogeneration. See [`AGENTS.md`](../AGENTS.md) for the full rule set.

## Schema

`candles`:

| Column | Type | Notes |
| --- | --- | --- |
| `symbol` | `TEXT` | `BASE/QUOTE`. |
| `interval_code` | `TEXT` | `1m` today. |
| `open_time` | `TIMESTAMPTZ` | Bucket start, UTC. |
| `open_price`, `high_price`, `low_price`, `close_price` | `NUMERIC(30,12)` | Mapped to `open`/`high`/`low`/`close` in the API. |
| `volume` | `NUMERIC(38,12)` | Nullable; current providers do not supply trade volume. |

The primary key is `(symbol, interval_code, open_time)`. The lookup index is
`(symbol, interval_code, open_time DESC)`.

## Where things live

| Concern | Location |
| --- | --- |
| Engine, pool, session, unit of work | [`src/db/session.py`](../src/db/session.py) |
| Candle SQL | [`src/candles/repository.py`](../src/candles/repository.py) |
| Background writer | [`src/candles/writer.py`](../src/candles/writer.py) |
| Schema | `migrations/versions/` (raw SQL) |

## Transactions

### Request sessions

`get_session` is the unit-of-work boundary:

```python
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
```

Repositories execute statements; they **must not** commit or roll back. A
request's reads see its own uncommitted writes.

### Background writes

The candle aggregator runs outside the request lifecycle. `CandleWriter` opens
its own `SessionFactory()` session, upserts the batch, and commits. Never reuse a
request-scoped session in a task.

A failed flush is logged and the batch is requeued for the next attempt;
ingestion and WebSocket streaming continue.

## SQL conventions

- Every statement is a module-level `text(...)` constant with bind parameters.
- No user value is interpolated into SQL.
- Rows map into Pydantic models with `model_validate(dict(row))`.
- Writes use `ON CONFLICT` for idempotent upserts.
- Timestamps are UTC and timezone-aware.

## Migrations

Hand-written raw SQL; autogenerate is disabled (`target_metadata = None`).

```bash
mise run revision "add candles"   # creates an empty file to fill in
mise run migrate                  # alembic upgrade head
```

- Write `CREATE ...` in `upgrade()` and the inverse in `downgrade()` via
  `op.execute(...)`.
- Filenames are timestamp-prefixed so they sort chronologically.
- The migration is the source of truth; the test suite rebuilds the schema by
  applying migrations.
- The chain keeps the original template `items` migration for compatibility,
  then drops `items` and creates `candles` in the FXStream migration. Fresh and
  existing template databases converge on the same schema.
- Inspect emitted SQL without a database: `uv run alembic upgrade head --sql`.

## Connection pool

Configured in [`src/db/session.py`](../src/db/session.py):
`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`,
`DB_POOL_TIMEOUT_SECONDS`, plus `pool_pre_ping`. `application_name` comes from
`APP_NAME`, and `DB_STATEMENT_TIMEOUT_MS` sets `statement_timeout` when non-zero.
See [configuration.md](configuration.md#database).

## Testing

`tests/candles/test_repository.py` exercises the native SQL against real
Postgres. Tests use the migration-built schema and truncate managed tables
between cases. See [testing.md](testing.md).
