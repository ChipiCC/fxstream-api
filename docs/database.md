# Database

Persistence is **native SQL over async SQLAlchemy Core + asyncpg**. SQLAlchemy is
used only as the async connection pool and transaction manager. There is no ORM
and no autogeneration. See [`AGENTS.md`](../AGENTS.md#native-sql) for the full
rule set.

## Where things live

| Concern | Location |
| --- | --- |
| Engine, pool, session, unit of work | [`src/db/session.py`](../src/db/session.py) |
| Repository contract | [`src/core/repository.py`](../src/core/repository.py) |
| Concrete SQL | `src/<domain>/repository.py` |
| Schema | `migrations/versions/` (raw SQL) |

## SQL conventions (short version)

- Every statement is a module-level `text(...)` constant, **parameterized** with
  bind parameters. The only dynamic SQL is a whitelist of column names.
- Reads map rows to models: `Schema.model_validate(dict(row))`.
- Writes use `RETURNING` to fetch the affected row and detect "not found" in one
  round-trip.
- Timestamps come from the database (`clock_timestamp()`), never Python.
- Primary keys are native Postgres `uuid` columns (`gen_random_uuid()`); bind
  `uuid.UUID` values directly.
- Raise `NotFoundError` / `ConflictError` from
  [`src/core/exceptions.py`](../src/core/exceptions.py).

## Transactions and the unit of work

The **session dependency owns the transaction boundary**, not the repository:

```python
# src/db/session.py
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

Consequences:

- A request's writes are **atomic**: if any step raises, everything rolls back.
  A multi-step business operation in a service is safe without reaching for the
  session.
- Repositories **must not** call `commit()`. They execute statements; the
  dependency commits when the request succeeds.
- Reads see uncommitted changes made earlier in the same request (same
  transaction), which is what tests and services rely on.

Because all writes in one request share a transaction, `CURRENT_TIMESTAMP` would
return the same value for every row. The items repository therefore uses
`clock_timestamp()` (and one value for `created_at`/`updated_at` on insert) so
distinct rows get distinct, increasing timestamps.

> If you later split reads onto a separate connection (read replicas), revisit
> this: the read would no longer see the request's uncommitted writes.

## Connection pool

Configured from settings in [`src/db/session.py`](../src/db/session.py):
`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`,
`DB_POOL_TIMEOUT_SECONDS`, plus `pool_pre_ping`. The pool sets
`application_name` (from `APP_NAME`) and, when `DB_STATEMENT_TIMEOUT_MS > 0`,
`statement_timeout`, so runaway queries cannot pin a connection. See
[configuration.md](configuration.md#database).

## Migrations

Hand-written raw SQL; autogenerate is disabled (`target_metadata = None`).

```bash
mise run revision "add orders"   # creates an empty file to fill in
mise run migrate                 # alembic upgrade head
```

- Write the `CREATE ...` in `upgrade()` and the inverse in `downgrade()` via
  `op.execute(...)`.
- Filenames are timestamp-prefixed (`2026_01_01_000000_add_orders.py`) so they
  sort chronologically.
- The migration is the source of truth; the test suite rebuilds the schema by
  applying migrations, so they are exercised on every run.
- Inspect emitted SQL without a database: `uv run alembic upgrade head --sql`.

## Testing repositories

The CRUD suite runs against **both** the Postgres repository and an in-memory
double, via a parametrized `item_repository` fixture. Add new implementations to
that parameter list instead of duplicating tests. See [testing.md](testing.md).
