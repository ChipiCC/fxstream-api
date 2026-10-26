# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.
Keep this file up to date when conventions, commands, or structure change.

## Project overview

A **production-ready FastAPI microservice template**. It ships an example
`items` domain to demonstrate the full request path (router → handler →
service → native SQL → Postgres). Generic names (`Item`) are intentional so they
can be renamed for a real domain.

Tech stack: Python 3.15, FastAPI, **native SQL over async SQLAlchemy Core +
asyncpg**, Alembic (raw-SQL migrations), Pydantic v2 / pydantic-settings,
structlog, Ruff, mypy, pytest, uv, mise.

> **No ORM.** SQLAlchemy is used only as the async connection pool and
> transaction manager. All queries are hand-written, parameterized SQL. See
> [Native SQL](#native-sql) below — it is the single most important convention
> in this repo.

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

## Architecture & layering

```
domain (router → handlers)  →  service  →  repository  →  db (engine, session)
                    ↘ models (Pydantic) ↗
```

The source root is `src/` and it is a **flat namespace** — there is no `app/`
package. Imports are absolute from the top level (`core.config`, `db.session`,
`items.service`, `app`).

- `src/app.py` — the application factory (`create_app`) and ASGI entrypoint
  (`app`). Wires middleware, exception handlers, and the domain routers.
- `src/core/` — cross-cutting: `config.py` (settings), `logging.py`,
  `exceptions.py` (+ handlers), `middleware.py` (request context/access log,
  security headers, rate limiting), `security.py` (API-key auth), `metrics.py`
  (Prometheus), `pagination.py` (`Page[T]`, `PaginationDep`), `repository.py`
  (`BaseRepository`), `version.py`.
- `src/db/` — concrete persistence infrastructure: async `engine`,
  `SessionFactory`, `get_session` + `SessionDep`. The `BaseRepository` contract
  lives in `core` because it is backend-agnostic (an in-memory fake implements
  it with no database).
- `src/<domain>/` — one self-contained package per domain (`items/`,
  `internal/`).

A domain is a package with a fixed shape:

```
src/items/
├── router.py         # APIRouter: wires paths to handlers (no logic)
├── handlers/         # one module per endpoint (create.py, list.py, ...)
├── service.py        # business logic; delegates persistence to the repository
├── repository.py     # data access: native SQL, owns transactions
├── models/           # Pydantic request/response models
└── dependencies.py   # domain DI aliases (e.g. ItemServiceDep)
```

- `router.py` + `handlers/` are the HTTP layer only. Parse/validate input, call
  a service, return a model. **No business logic, no SQL.**
- `service.py` — business logic only. It delegates persistence to a repository
  and must not touch the session or write SQL.
- `repository.py` — the data-access layer. Subclasses `BaseRepository` (from
  `core/repository.py`), holds all the hand-written SQL, and owns transaction
  boundaries (`commit`).
- `models/` — Pydantic request/response models. Queries return rows that are
  validated straight into `*Read` models.
- `internal/` is the non-domain domain: service metadata and health probes,
  mounted at the root (`/`, `/health/*`) outside the versioned API prefix.

There is **no ORM models package** — the schema lives in Alembic migrations and
the queries live in repositories.

### Adding a new domain

1. `mise run revision "add <name>"` — write the `CREATE TABLE` / `CREATE INDEX`
   as raw SQL in `upgrade()` (and the inverse in `downgrade()`).
2. `src/<domain>/models/<name>.py` — `XCreate`, `XUpdate`, `XRead` (mirror the
   columns); re-export from `models/__init__.py`.
3. `src/<domain>/repository.py` — a `<Name>Repository(BaseRepository[...])`
   taking `AsyncSession`, with the SQL as module-level `text(...)` constants;
   the write methods commit.
4. `src/<domain>/service.py` — a `<Name>Service` taking the repository;
   business logic only.
5. `src/<domain>/handlers/<endpoint>.py` — one module per endpoint; re-export
   from `handlers/__init__.py`.
6. `src/<domain>/router.py` — `APIRouter(prefix="/<names>", tags=[...])` wiring
   each handler with `add_api_route`.
7. `src/<domain>/dependencies.py` — the repository and service dependency
   aliases.
8. Register the router in `src/app.py` (pass `prefix=settings.api_v1_prefix` for
   public domains; mount internal domains at the root).
9. Write tests under `tests/<domain>/`, then run `mise run check`. The test
   schema is built from the migrations automatically — there is no separate DDL
   to keep in sync.

## Native SQL

**Rule: every SQL statement is written by hand and executed through
`sqlalchemy.text()`.** Do not introduce the ORM (`DeclarativeBase`, `Mapped`,
`select()`/`session.add()`), and do not use `--autogenerate`.

### Rules

- **Always parameterize.** Use bind parameters (`:name`) for every value. Never
  interpolate user input into a SQL string. The only thing built dynamically is
  a set of **column names from a fixed whitelist** (see `ItemRepository.update`),
  which is safe and marked with `# noqa: S608`.
- **Keep SQL as module-level constants.** Define statements once at the top of
  the repository module (`_GET_ITEM`, `_INSERT_ITEM`, …) and reuse them. Do not
  build SQL inline inside request handlers.
- **Return rows, map to schemas.** Use `result.mappings()` and
  `Schema.model_validate(dict(row))`. Repositories return Pydantic schemas, not
  dicts and not ORM objects.
- **Use `RETURNING`.** `INSERT`/`UPDATE`/`DELETE … RETURNING` fetch the affected
  row in one round-trip and let you detect "not found" without a second query.
- **Timestamps come from the database.** Columns default to
  `CURRENT_TIMESTAMP`; set `updated_at` on updates. Do not generate timestamps
  in Python. Because a request runs in one transaction, prefer
  `clock_timestamp()` where rows written in the same request must be ordered
  (see `ItemRepository`).
- **Native UUID keys.** Primary keys are PostgreSQL `uuid` columns defaulted
  with `gen_random_uuid()`. Bind `uuid.UUID` values directly (asyncpg encodes
  them); never stringify them. Let the database generate the id and read it
  back with `RETURNING`.
- **Transactions are owned by the session, not the repository.**
  `get_session` (in `db/session.py`) is a unit of work: it commits once when the
  request succeeds and rolls back if anything raises. Repository methods must
  **not** call `commit()` (or `rollback()`); they just execute statements. This
  keeps multi-step service operations atomic. See `docs/database.md`.
- **Errors.** Raise `NotFoundError` / `ConflictError` / `AppError` (and friends:
  `BadRequestError`, `UnauthorizedError`, `ForbiddenError`,
  `TooManyRequestsError`, `ServiceUnavailableError`) from
  `core/exceptions.py`. Do not return error dicts.

### Example

```python
_GET_ITEM = text("SELECT id, name, description, created_at, updated_at FROM items WHERE id = :id")


async def get(self, item_id: uuid.UUID) -> ItemRead:
    row = (await self.session.execute(_GET_ITEM, {"id": item_id})).mappings().one_or_none()
    if row is None:
        raise NotFoundError(f"Item {item_id} not found")
    return ItemRead.model_validate(dict(row))
```

## Conventions

- **Async everywhere.** All endpoint/service/repository/DB code is `async def`.
  The DB session comes from `get_session` (an `AsyncSession`).
- **Dependency injection.** Shared aliases live next to what they wrap:
  `SessionDep` in `db/session.py`, `PaginationDep` in `core/pagination.py`, and
  domain aliases in `<domain>/dependencies.py` (e.g. `ItemRepositoryDep`,
  `ItemServiceDep`). Prefer adding a new alias over repeating `Depends(...)`.
- **Type hints are mandatory.** mypy runs in strict mode. New public functions
  need fully-annotated signatures; avoid `Any` and untyped decorators.
- **Pagination.** Use `limit`/`offset` via `PaginationDep` and return `Page[T]`,
  both from `core/pagination.py`.
- **Style.** Line length 100, double quotes, Ruff is the source of truth.
  Do not hand-format; run `mise run fix`.
- **Imports.** `from __future__ import annotations` at the top of modules.
  Absolute imports rooted at the top-level package (`core.`, `db.`, `items.`, …)
  or the `app` module.
- **No `print`.** Use `get_logger(__name__)` (structlog). Ruff bans `T20`.
- **Cross-cutting HTTP concerns live in `core/`.** Auth, CORS, security headers,
  rate limiting, and metrics are wired once in `app.py` / `core/middleware.py`.
  Protect a public router with `dependencies=[Depends(require_api_key)]` rather
  than hand-rolling checks in handlers.
- **Document changes.** User-facing docs live in `docs/` (one page per topic,
  indexed by `docs/README.md`). Add new settings to `.env.local.example` and the
  table in `docs/configuration.md`.
- **Comments.** Keep them short, lowercase, with no trailing period, and match
  the surrounding style. Use `# --- Section ---` for section headers. Lint
  directives (`# noqa`, `# type: ignore`) are always fine.

## Testing

- Tests live in `tests/`, mirroring the domain layout (e.g.
  `tests/items/test_items.py`, `tests/internal/test_health.py`, `tests/core/…`).
- They run against a **real PostgreSQL database** — there is no SQLite path.
  Start one with `mise run db:up` (Docker Compose) before running the suite.
- The target is the `TEST_DATABASE_URL` env var (default
  `postgresql+asyncpg://postgres:postgres@localhost:5432/app_test`).
- The schema is built by applying the **Alembic migrations in a subprocess**
  (see `tests/conftest.py`), so the suite exercises the migrations too. There is
  no separate test schema to maintain.
- Fixtures: `database_url` (session-scoped, migrated DB), `engine`, `session`
  (truncates `items` for isolation), `client` (httpx ASGI client).
- Repository contract tests live in `tests/items/conftest.py` as an
  `item_repository` fixture parametrized over **both** the Postgres
  `ItemRepository` and the in-memory double in `tests/helpers/repositories.py`.
  Add new repository implementations (or fakes) to that parameter list rather
  than duplicating the CRUD suite.
- `pytest-asyncio` is in `auto` mode — just write `async def test_...`.
- The DB dependency is overridden per test, so the app's own engine is unused.
- Cover the happy path **and** error paths (404, 422, validation).
- Warnings are errors (`filterwarnings = error`); don't introduce new warnings.
- **Coverage must declare `concurrency = ["greenlet", "thread"]`** (already set
  in `pyproject.toml`). SQLAlchemy's async engine runs through greenlet and
  FastAPI uses a threadpool; without this, coverage silently drops every line
  after a DB `await`. Do not remove it.

## Migrations

- Alembic is configured with `target_metadata = None`; **autogenerate is
  disabled**. `mise run revision "msg"` creates an empty file — fill `upgrade()`
  / `downgrade()` with raw SQL via `op.execute("...")`.
- The migration is the source of truth for the schema; keep it readable and
  one logical change per file.
- Filenames are prefixed with the creation timestamp (UTC) as
  `year_month_day_HMS` via `file_template` in `alembic.ini`, e.g.
  `2026_01_01_000000_create_items.py`, so they sort chronologically. The
  internal revision id stays Alembic's default.
- `migrations/env.py` resolves the URL from, in order: `alembic -x db_url=...`
  (used by the test suite), a pre-set `sqlalchemy.url`, then app settings.
- Inspect emitted SQL without a database: `uv run alembic upgrade head --sql`.

## Configuration & secrets

- Add new settings to `Settings` in `core/config.py` with a sane default, and
  document them in `.env.local.example`.
- Read settings via `get_settings()` (cached); never call `os.environ` directly.
  The single exception is the production check in `core/config.py`, which must
  run before any dotfile is read.
- **Never commit real secrets.** `.env.local` is gitignored; only
  `.env.local.example` ships. Production reads real env vars only — no dotfile.

## Do not

- Do not add an ORM, ORM models, or `--autogenerate` migrations.
- Do not interpolate values into SQL strings — bind them.
- Do not edit `.venv/`, `uv.lock` by hand, or generated files in
  `__pycache__`/caches. Regenerate with `uv lock`.
- Do not bypass the service layer from a handler (and do not let a service
  reach for the session — it goes through its repository).
- Do not add dependencies without updating `uv.lock` (`uv add <pkg>`).
- Do not weaken mypy/Ruff config to make code pass; fix the code.
- Do not lower the coverage threshold (`fail_under` in `pyproject.toml`).
- Do not commit from a repository — the session dependency owns the transaction.
- Do not add narration comments (e.g. `# increment counter`) or restate what the
  code already says — see [Comments](#conventions).

## Environment

- Source root: `src/` — a flat namespace, so `import app`, `import core`, … work
  from the repo root. Packaging is configured via `hatchling`.
- Python ≥ 3.15. Tool versions pinned in `mise.toml`.
- Tests set `pythonpath = ["src"]`.
