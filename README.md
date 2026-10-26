# FastAPI Service Template

A production-ready template for building FastAPI microservices.

- **Runtime:** Python 3.15, FastAPI, Uvicorn
- **Data:** native SQL over async SQLAlchemy Core + asyncpg, Alembic raw-SQL migrations, PostgreSQL with native `uuid` keys (no ORM)
- **Architecture:** layered `domain → service → repository → db`, with a generic `BaseRepository` CRUD contract and a request-scoped unit of work
- **Config:** `pydantic-settings` (12-factor, `.env` support, production guards)
- **Security:** opt-in API-key auth, CORS, security headers, trusted hosts, in-process rate limiting
- **Observability:** structured JSON logging, request IDs + access logs, Prometheus metrics
- **Quality:** Ruff (lint + format), mypy (strict), pytest + coverage gate
- **Ops:** Dockerfile (multi-stage, non-root), Docker Compose, GitHub Actions CI, Dependabot
- **Tooling:** [uv](https://docs.astral.sh/uv/) for deps, [mise](https://mise.jdx.dev/) for tool versions & tasks

## Documentation

Full documentation lives in [`docs/`](docs/README.md), split by topic:

| Topic | Description |
| --- | --- |
| [Architecture](docs/architecture.md) | Layering, request path, and the no-ORM policy |
| [Configuration](docs/configuration.md) | Every setting, secrets, and production validation |
| [Authentication](docs/authentication.md) | Opt-in API-key auth and swapping in JWT/OAuth |
| [CORS](docs/cors.md) | Browser cross-origin setup |
| [Security](docs/security.md) | Headers, trusted hosts, rate limiting, checklist |
| [Metrics](docs/metrics.md) | Prometheus instrumentation and `/metrics` |
| [Observability](docs/observability.md) | Logging, request IDs, access logs, tracing (roadmap) |
| [Database](docs/database.md) | Native SQL, the unit-of-work, pooling, migrations |
| [Testing](docs/testing.md) | Fixtures, contract tests, coverage |
| [Operations](docs/operations.md) | Docker, migrations, health probes, shutdown |
| [Dependencies](docs/dependencies.md) | Dependabot updates and patch auto-merge |
| [Roadmap](docs/roadmap.md) | Deliberately out-of-scope items |

## Project layout

```
.
├── src/
│   ├── app.py               # app factory + ASGI entrypoint (middleware, routers)
│   ├── core/                # config, logging, errors, middleware, security,
│   │                        # pagination, metrics, BaseRepository
│   ├── db/                  # async engine + session (unit of work)
│   ├── internal/            # internal domain: metadata + health probes
│   │   ├── router.py
│   │   ├── handlers/
│   │   └── models/
│   └── items/               # example domain
│       ├── router.py        # wires paths to handlers
│       ├── handlers/        # one module per endpoint
│       ├── service.py       # business logic (thin layer over the repository)
│       ├── repository.py    # ItemRepository: native SQL
│       ├── models/          # Pydantic request/response models
│       └── dependencies.py
├── migrations/              # Alembic environment + raw-SQL versions
├── tests/                   # pytest suite (mirrors the domain layout)
├── docs/                    # documentation (see above)
├── Dockerfile / compose.yaml
└── pyproject.toml           # deps + tool config
```

**Layering rule:** `domain → service → repository → db`. Each domain lives in
its own `src/<domain>/` package: the router/handlers stay thin, the service
holds business logic and delegates persistence to a repository, and the
repository owns the hand-written SQL. The session dependency owns the
transaction. Rows are mapped straight into Pydantic models. There is **no ORM** —
see [`docs/database.md`](docs/database.md) and [`AGENTS.md`](AGENTS.md).

## Getting started

```bash
mise install        # install Python 3.15 + uv
mise run sync       # create .venv and install dependencies
cp .env.local.example .env.local
mise run db:up      # start Postgres (Docker Compose)
mise run migrate    # apply migrations
mise run dev        # http://localhost:8000/docs
```

Run the whole stack (API + Postgres) with Docker:

```bash
mise run docker:up
```

## Common tasks

| Task | Command |
| --- | --- |
| Install/refresh deps | `mise run sync` |
| Dev server | `mise run dev` |
| Lint | `mise run lint` |
| Format | `mise run format` |
| Autofix | `mise run fix` |
| Type check | `mise run typecheck` |
| Tests | `mise run test` |
| Everything | `mise run check` |
| Start/stop Postgres | `mise run db:up` / `db:down` |
| New migration | `mise run revision "add foo"` |
| Apply migrations | `mise run migrate` |

Without mise, the equivalents are `uv run <tool>` (e.g. `uv run pytest`).

## Testing

Tests run against a **real PostgreSQL database** (no SQLite). Start one first
with `mise run db:up`, then:

```bash
mise run test
```

The connection is taken from `TEST_DATABASE_URL` (default
`postgresql+asyncpg://postgres:postgres@localhost:5432/app_test`). The schema is
built by applying the Alembic migrations, so the suite also validates them.
Coverage is enforced at 90%. See [`docs/testing.md`](docs/testing.md).

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Service metadata |
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe (checks DB, `503` when down) |
| GET | `/metrics` | Prometheus metrics (when enabled) |
| GET/POST | `/api/v1/items` | List / create items |
| GET/PATCH/DELETE | `/api/v1/items/{id}` | Read / update / delete an item |
| GET | `/docs`, `/redoc`, `/openapi.json` | API docs |

Protected routes accept the `X-API-Key` header when `API_KEYS` is configured —
see [`docs/authentication.md`](docs/authentication.md).

## Configuration

All settings live in `src/core/config.py` and are read from environment
variables (plus `.env.local` outside production). See
[`.env.local.example`](.env.local.example) for the full list and
[`docs/configuration.md`](docs/configuration.md) for reference. The app refuses
to start with insecure defaults when `ENVIRONMENT=production`.

## License

MIT — see [LICENSE](LICENSE).
