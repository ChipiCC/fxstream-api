# Testing

Tests live in `tests/` and mirror the domain layout. They run against a **real
PostgreSQL database** — there is no SQLite path. The schema is built by applying
the Alembic migrations in a subprocess, so every run also exercises migrations.

## Running

```bash
mise run db:up     # start Postgres (docker compose up -d db)
mise run test      # uv run pytest
```

The target is `TEST_DATABASE_URL`, defaulting to
`postgresql+asyncpg://postgres:postgres@localhost:5432/app_test`.

`pytest-asyncio` is in `auto` mode, so write plain `async def test_...`.

## Layout

```
tests/
├── conftest.py            # database_url, engine, session, client fixtures
├── core/                  # config, middleware, metrics, security
├── db/                    # unit-of-work session
├── internal/              # metadata + health probes
├── items/                 # domain: endpoints + repository contract
└── helpers/repositories.py  # in-memory repository doubles
```

## Fixtures

| Fixture | Scope | Purpose |
| --- | --- | --- |
| `database_url` | session | Migrated, empty test database (`downgrade base` → `upgrade head`). |
| `engine` | function | Async engine bound to the test database (`NullPool`). |
| `session` | function | Session on a clean schema (all tables truncated). |
| `client` | function | `httpx` ASGI client with the DB dependency overridden. |

The `session` fixture truncates **every** table except `alembic_version`, so new
domains are isolated automatically — no fixture edits required.

## Repository contract tests

`tests/items/conftest.py` parametrizes `item_repository` over the Postgres
`ItemRepository` and the in-memory double in `tests/helpers/repositories.py`:

```python
@pytest.fixture(params=["in_memory", "postgres"])
async def item_repository(request, session): ...
```

A single CRUD suite (`tests/items/test_item_repository.py`) holds both
implementations to the same behaviour. When you add a domain, add a similar
parametrized fixture and a shared contract test rather than duplicating cases.

## What to cover

- Happy path **and** error paths (404, 422, validation).
- New middleware and dependencies (e.g. auth `401`, readiness `503`, rate limit
  `429`).
- Configuration edge cases (production guard, DSN encoding).

## Coverage

Coverage is enforced: `pyproject.toml` sets `fail_under = 90`. The suite reports
`term-missing` and writes `coverage.xml`. Keep it green; do not lower the
threshold to make code pass.

> **Important:** coverage declares `concurrency = ["greenlet", "thread"]`.
> SQLAlchemy's async engine runs through greenlet and FastAPI uses a threadpool;
> without this, coverage silently drops every line after a DB `await`. Do not
> remove it.

## Warnings are errors

`filterwarnings = ["error"]` — do not introduce new warnings.
