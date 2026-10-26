# Operations

## Local development

```bash
mise install         # Python 3.15 + uv
mise run sync        # create .venv, install dependencies
cp .env.local.example .env.local
mise run db:up       # start Postgres
mise run migrate     # apply migrations
mise run dev         # http://localhost:8000/docs
```

## Docker

The [`Dockerfile`](../Dockerfile) is multi-stage: dependencies are resolved into
a self-contained venv in the builder, then copied into a slim, non-root runtime
image. `STOPSIGNAL SIGTERM` lets Uvicorn shut down gracefully.

Run the whole stack (API + Postgres) with Compose:

```bash
mise run docker:up     # docker compose up --build
```

Compose runs `alembic upgrade head` before starting Uvicorn:

```yaml
command: sh -c "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8000"
```

### Scaling workers

The image starts a single Uvicorn process. For CPU-bound throughput, run
multiple workers behind a process manager or increase replicas:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
```

> The in-process rate limiter and any in-memory cache are **per worker**. Use a
> shared store or an edge limiter when running more than one worker/replica. See
> [security.md](security.md#rate-limiting).

## Migrations at deploy time

- Run `alembic upgrade head` as a release/deploy step (as Compose does), not
  inside application startup, so rollout is deterministic.
- Migrations are forward-only in production; keep `downgrade()` correct for
  local/test use.
- Inspect SQL without a database: `uv run alembic upgrade head --sql`.

## Health probes

| Endpoint | Use | Behaviour |
| --- | --- | --- |
| `GET /health/live` | Liveness | `200` while the process is up; never touches dependencies. |
| `GET /health/ready` | Readiness | `200` when the database is reachable, `503` otherwise. |

Wire them to your orchestrator. Kubernetes example:

```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8000 }
readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }
```

Because readiness returns `503` on a database outage, traffic stops routing to a
degraded instance instead of failing requests.

## Graceful shutdown

The app lifespan disposes the database engine on shutdown. On `SIGTERM` Uvicorn
stops accepting connections and drains in-flight requests before the process
exits.

## Configuration in production

Set at minimum: `ENVIRONMENT=production`, `DEBUG=false`, `DOCS_ENABLED=false`,
`ALLOWED_HOSTS`, `API_KEYS`, and real database credentials. The app refuses to
start otherwise — see
[configuration.md](configuration.md#production-validation).

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs lint, format
check, mypy, `pip-audit`, and the test suite (with the coverage gate) against a
Postgres service on every push/PR. Dependabot keeps dependencies and Actions up
to date — see [dependencies.md](dependencies.md).
