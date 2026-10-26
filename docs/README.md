# Documentation

Reference and how-to documentation for the FastAPI service template. Start with
the [architecture overview](architecture.md) if you are new to the codebase, or
jump straight to a topic below.

## Categories

| Topic | What it covers |
| --- | --- |
| [Architecture](architecture.md) | Layering (`domain → service → repository → db`), the request path, and why there is no ORM. |
| [Configuration](configuration.md) | Every setting, source precedence, `.env.local`, secrets, and production validation. |
| [Authentication](authentication.md) | Opt-in API-key auth, wiring new routes, and how to swap in JWT/OAuth. |
| [CORS](cors.md) | Browser cross-origin setup and preflight behaviour. |
| [Security](security.md) | Security headers, trusted hosts, rate limiting, and the hardening checklist. |
| [Metrics](metrics.md) | Prometheus instrumentation and the `/metrics` endpoint. |
| [Observability](observability.md) | Structured logging, request IDs, access logs, and tracing (roadmap). |
| [Database](database.md) | Native SQL, the unit-of-work transaction model, pooling, and migrations. |
| [Testing](testing.md) | Test layout, fixtures, repository contract tests, and coverage. |
| [Operations](operations.md) | Docker, migrations at deploy time, health probes, and shutdown. |
| [Dependencies](dependencies.md) | Dependabot version/security updates and the patch auto-merge workflow. |
| [Roadmap](roadmap.md) | Deliberately out-of-scope items and where to add them. |

## Conventions

The code and docs follow the conventions in [`AGENTS.md`](../AGENTS.md) — most
importantly, **all SQL is hand-written** and executed through
`sqlalchemy.text()`. There is no ORM.

## Keeping docs current

When a change touches a documented area, update the matching page in this
folder and, if it adds a setting, the table in
[configuration.md](configuration.md) and `.env.local.example`.
