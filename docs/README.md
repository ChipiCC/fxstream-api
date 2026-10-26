# Documentation

Reference and how-to documentation for FXStream API. Start with the
[high-level design](high-level-design.md) for product scope, then
[architecture](architecture.md) for how the process is wired.

## Categories

| Topic | What it covers |
| --- | --- |
| [High-Level Design](high-level-design.md) | Product scope, components, domain model, API contract, and key decisions. |
| [Architecture](architecture.md) | Runtime flow, package layout, request path, and invariants. |
| [Market Data](market-data.md) | Rates, staleness, quotes, candles, and precision. |
| [Providers](providers.md) | Binance, Frankfurter, resilience, and adding a provider. |
| [WebSocket](websocket.md) | Subscription protocol, tick frames, and backpressure. |
| [Configuration](configuration.md) | Every setting, source precedence, secrets, and production validation. |
| [Authentication](authentication.md) | Opt-in API-key auth and how to swap in JWT/OAuth. |
| [CORS](cors.md) | Browser cross-origin setup and preflight behaviour. |
| [Security](security.md) | Security headers, trusted hosts, rate limiting, and the hardening checklist. |
| [Metrics](metrics.md) | Prometheus instrumentation and the `/metrics` endpoint. |
| [Observability](observability.md) | Structured logging, request IDs, access logs, and tracing (roadmap). |
| [Database](database.md) | Native SQL, the unit-of-work model, candles, pooling, and migrations. |
| [Testing](testing.md) | Test layout, fixtures, fakes, and coverage. |
| [Operations](operations.md) | Docker, migrations, health probes, shutdown, and scaling. |
| [Dependencies](dependencies.md) | Dependabot version/security updates and the patch auto-merge workflow. |
| [Roadmap](roadmap.md) | Deliberately out-of-scope items and where to add them. |

## Conventions

The code and docs follow the conventions in [`AGENTS.md`](../AGENTS.md) — most
importantly, **all prices are `Decimal`**, **all SQL is hand-written**, and the
event bus must never block on a slow WebSocket client. There is no ORM.

## Keeping docs current

When a change touches a documented area, update the matching page in this
folder and, if it adds a setting, the table in
[configuration.md](configuration.md) and `.env.local.example`.
