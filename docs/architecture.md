# Architecture

## Layers

```
HTTP (router → handlers)  →  service  →  repository  →  db (engine, session)
                     ↘  models (Pydantic)  ↗
```

- **router/handlers** — the HTTP layer. Parse/validate input, call a service,
  return a model. No business logic, no SQL.
- **service** — business logic only. Delegates persistence to a repository and
  never touches the session or writes SQL.
- **repository** — the data-access layer. Owns all hand-written SQL and maps rows
  into Pydantic `*Read` models. Does **not** manage transactions (see
  [database.md](database.md)).
- **db** — the async engine and the `get_session` unit of work.

A domain is a self-contained package:

```
src/items/
├── router.py         # APIRouter: wires paths → handlers (no logic)
├── handlers/         # one module per endpoint (create.py, list.py, ...)
├── service.py        # business logic
├── repository.py     # native SQL
├── models/           # Pydantic request/response models
└── dependencies.py   # domain DI aliases (ItemServiceDep, ...)
```

`src/internal/` is the non-domain domain (metadata + health probes) mounted at
the root, outside the versioned API prefix.

## Request path

1. Middleware runs (outer → inner): request context/access log, metrics, CORS,
   security headers, trusted host, rate limiting. See
   [observability.md](observability.md) and [security.md](security.md).
2. FastAPI routes to a handler in `src/<domain>/handlers/`.
3. The handler calls a service (injected via a `*ServiceDep` alias).
4. The service calls a repository method (native SQL, `RETURNING`, parameterized).
5. `get_session` commits the request's transaction on success, rolls back on
   error.

## Why no ORM

The repository layer uses **native SQL over async SQLAlchemy Core + asyncpg**.
SQLAlchemy is only the connection pool and transaction manager. This keeps
queries explicit and reviewable, avoids lazy-loading surprises on async code,
and makes the schema (`migrations/`) the single source of truth. See
[database.md](database.md) and [`AGENTS.md`](../AGENTS.md).

## Adding a domain

See the step-by-step list in [`AGENTS.md`](../AGENTS.md#adding-a-new-domain).
In short: migration → models → repository → service → handlers → router →
dependencies → register the router in `src/app.py` → tests.
