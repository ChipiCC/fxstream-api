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

### Scaling

**Run one worker per FXStream process group.** Rates, quotes, provider state,
WebSocket subscriptions, the event bus, and the rate limiter are in memory.
Multiple workers/replicas would serve inconsistent prices and split quote
stores.

To scale horizontally, add a shared pub/sub and quote store (Redis is the
obvious candidate), then move the provider ingestion to a single writer or
leader. Keep the candle aggregator single-writer as well. See
[roadmap.md](roadmap.md).

## Migrations at deploy time

- Run `alembic upgrade head` as a release/deploy step (as Compose does), not
  inside application startup, so rollout is deterministic.
- Migrations are forward-only in production; keep `downgrade()` correct for
  local/test use.
- Inspect SQL without a database: `uv run alembic upgrade head --sql`.

## Health probes

| Endpoint | Use | Behaviour |
| --- | --- | --- |
| `GET /health` | Aggregate | Same readiness check as `/health/ready`. |
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

On shutdown the lifespan:

1. stops provider adapters and cancels their supervised tasks;
2. stops the candle aggregator and flushes current candles;
3. disposes the database engine.

On `SIGTERM` Uvicorn stops accepting connections and drains in-flight requests
before the process exits.

## Configuration in production

Set at minimum: `ENVIRONMENT=production`, `DEBUG=false`, `DOCS_ENABLED=false`,
`ALLOWED_HOSTS`, `API_KEYS`, real database credentials, and production provider
symbols/staleness thresholds. The app refuses to start otherwise — see
[configuration.md](configuration.md#production-validation).

## Platform notes

- Run the backend on a platform that supports long-lived WebSocket connections
  (Render, Fly.io, or a container platform). Configure provider symbols,
  staleness thresholds, spreads, and database credentials as environment
  variables.
- Run `alembic upgrade head` as a release step before starting the new version.
- Deploy the frontend separately (for example on Vercel) and add its origin to
  `CORS_ORIGINS`. Point the WebSocket client at `wss://<api-host>/v1/ws/rates`.
- Keep one backend worker/replica until shared state (Redis) is added.

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs lint, format
check, mypy, `pip-audit`, and the test suite (with the coverage gate) against a
Postgres service on every push/PR. Dependabot keeps dependencies and Actions up
to date — see [dependencies.md](dependencies.md).
